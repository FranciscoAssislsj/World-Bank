"""Pipeline da bronze: grava as respostas da API como vieram.

Para cada requisição (cadastros, metadados dos indicadores e observações),
busca todas as páginas e compara com a última carga gravada. Só grava quando o
conteúdo mudou (D-010), e grava a requisição inteira numa transação (D-011).
"""

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

import psycopg

from world_bank.config import Settings
from world_bank.extract.client import ApiPage, WorldBankClient
from world_bank.extract.endpoints import (
    DIMENSION_PATHS,
    fetch_dimension,
    fetch_indicator_metadata,
    fetch_observations,
)
from world_bank.load.postgres import (
    insert_pages,
    json_hash,
    latest_payload_hashes,
    params_hash,
)

logger = logging.getLogger(__name__)

type RequestStatus = Literal["inserted", "unchanged"]


@dataclass(frozen=True)
class RequestResult:
    """Resultado da gravação de uma requisição.

    Attributes:
        endpoint: Caminho do endpoint (ex.: ``"country"``).
        params_hash: Identificador da requisição.
        pages: Páginas buscadas na API.
        records: Soma dos registros de todas as páginas.
        status: ``"inserted"`` se gravou, ``"unchanged"`` se igual à última carga.
    """

    endpoint: str
    params_hash: str
    pages: int
    records: int
    status: RequestStatus


def load_request(
    conn: psycopg.Connection, run_id: UUID, pages: list[ApiPage]
) -> RequestResult:
    """Grava as páginas de uma requisição, se mudaram desde a última carga.

    A requisição é igual quando tem o mesmo número de páginas e cada página tem
    o mesmo ``payload_hash``, na mesma ordem.

    Args:
        conn: Conexão em modo autocommit.
        run_id: Identificador da execução.
        pages: Todas as páginas da requisição, na ordem.

    Returns:
        O que foi feito com a requisição.
    """
    request_hash = params_hash(pages[0])
    new_hashes = [json_hash(page.payload) for page in pages]
    with conn.transaction():
        changed = latest_payload_hashes(conn, request_hash) != new_hashes
        if changed:
            insert_pages(conn, run_id, pages)
    result = RequestResult(
        endpoint=pages[0].path,
        params_hash=request_hash,
        pages=len(pages),
        records=sum(len(page.records) for page in pages),
        status="inserted" if changed else "unchanged",
    )
    logger.info(
        "bronze request loaded",
        extra={
            "endpoint": result.endpoint,
            "pages": result.pages,
            "records": result.records,
            "status": result.status,
        },
    )
    return result


def group_by_request(pages: Iterable[ApiPage]) -> Iterator[list[ApiPage]]:
    """Agrupa páginas consecutivas da mesma requisição.

    O grupo é entregue assim que chega a última página da requisição
    (``page >= pages``), sem esperar a próxima. Assim, se a requisição seguinte
    falhar, a anterior já foi entregue e gravada. Se a busca de uma página
    falhar no meio, o erro sobe antes de o grupo incompleto ser entregue.

    Args:
        pages: Páginas na ordem em que o cliente as devolve.

    Yields:
        Lista com todas as páginas de uma requisição.
    """
    current: list[ApiPage] = []
    for page in pages:
        if current and params_hash(page) != params_hash(current[0]):
            yield current
            current = []
        current.append(page)
        if page.page >= page.pages:
            yield current
            current = []
    if current:
        yield current


def extract_all(
    client: WorldBankClient, settings: Settings, start_year: int, end_year: int
) -> Iterator[ApiPage]:
    """Encadeia todas as extrações da bronze: cadastros, indicadores e observações.

    Args:
        client: Cliente da API.
        settings: Configurações (indicadores e fonte).
        start_year: Primeiro ano das observações.
        end_year: Último ano das observações.

    Yields:
        As páginas, uma requisição depois da outra.
    """
    for dimension in DIMENSION_PATHS:
        yield from fetch_dimension(client, dimension)
    yield from fetch_indicator_metadata(client, settings.indicators)
    yield from fetch_observations(
        client, settings.indicators, start_year, end_year, settings.source_id
    )


def run_bronze(
    client: WorldBankClient,
    conn: psycopg.Connection,
    settings: Settings,
    start_year: int,
    end_year: int,
) -> list[RequestResult]:
    """Executa a carga da bronze de ponta a ponta.

    Args:
        client: Cliente da API.
        conn: Conexão em modo autocommit.
        settings: Configurações.
        start_year: Primeiro ano das observações.
        end_year: Último ano das observações.

    Returns:
        O resultado de cada requisição, na ordem.

    Raises:
        ApiResponseError: Se uma requisição falhar de forma definitiva. As
            requisições anteriores já gravadas permanecem no banco.
    """
    run_id = uuid4()
    logger.info("bronze run started", extra={"run_id": str(run_id)})
    pages = extract_all(client, settings, start_year, end_year)
    results = [load_request(conn, run_id, group) for group in group_by_request(pages)]
    logger.info(
        "bronze run finished",
        extra={
            "run_id": str(run_id),
            "requests": len(results),
            "inserted": sum(r.status == "inserted" for r in results),
            "unchanged": sum(r.status == "unchanged" for r in results),
        },
    )
    return results
