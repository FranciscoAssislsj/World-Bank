"""Endpoints da World Bank API v2 usados pelo pipeline.

Cada função só monta o caminho e os parâmetros e devolve as páginas brutas.
"""

import re
from collections.abc import Iterator
from typing import Literal

from world_bank.extract.client import ApiPage, WorldBankClient

type Dimension = Literal[
    "region", "income_level", "lending_type", "country", "source", "topic"
]

DIMENSION_PATHS: dict[str, str] = {
    "region": "region",
    "income_level": "incomelevel",
    "lending_type": "lendingtypes",
    "country": "country",
    "source": "sources",
    "topic": "topic",
}

# Limites da API (doc_api.md §7): até 60 indicadores por requisição e URL de até
# 4000 caracteres. 3000 caracteres de códigos deixam folga para o resto da URL.
MAX_INDICATORS_PER_REQUEST = 60
MAX_INDICATOR_CHARS = 3000

_INDICATOR_ID = re.compile(r"^[A-Za-z0-9._]+$")


def fetch_dimension(client: WorldBankClient, dimension: Dimension) -> Iterator[ApiPage]:
    """Busca todas as páginas de um endpoint de cadastro (região, país etc.).

    Args:
        client: Cliente da API.
        dimension: Nome da dimensão (chave de ``DIMENSION_PATHS``).

    Returns:
        Iterador sobre as páginas brutas.

    Raises:
        ValueError: Se a dimensão não for conhecida.
    """
    try:
        path = DIMENSION_PATHS[dimension]
    except KeyError as exc:
        raise ValueError(f"dimensão desconhecida: {dimension}") from exc
    return client.iter_pages(path)


def fetch_indicator_metadata(
    client: WorldBankClient, indicator_ids: list[str]
) -> Iterator[ApiPage]:
    """Busca o cadastro de cada indicador (nome, fonte, tópicos).

    Args:
        client: Cliente da API.
        indicator_ids: Códigos dos indicadores.

    Yields:
        As páginas brutas de ``/indicator/{id}``, um indicador por vez.

    Raises:
        ValueError: Se algum código tiver caracteres inválidos.
    """
    for indicator_id in indicator_ids:
        _check_indicator_id(indicator_id)
        yield from client.iter_pages(f"indicator/{indicator_id}")


def fetch_observations(
    client: WorldBankClient,
    indicator_ids: list[str],
    start_year: int,
    end_year: int,
    source_id: int,
) -> Iterator[ApiPage]:
    """Busca as observações de todos os países para os indicadores informados.

    Os indicadores são agrupados em lotes que respeitam os limites da API.

    Args:
        client: Cliente da API.
        indicator_ids: Códigos dos indicadores.
        start_year: Primeiro ano.
        end_year: Último ano.
        source_id: Fonte da API (ex.: 2 = WDI), obrigatória com vários indicadores.

    Yields:
        As páginas brutas de ``/country/all/indicator/{ids}``.

    Raises:
        ValueError: Se o período for inválido ou algum código for inválido.
    """
    if start_year > end_year:
        raise ValueError(f"start_year ({start_year}) > end_year ({end_year})")
    params = {"date": f"{start_year}:{end_year}", "source": str(source_id)}
    for chunk in chunk_indicators(indicator_ids):
        yield from client.iter_pages(f"country/all/indicator/{';'.join(chunk)}", params)


def chunk_indicators(
    indicator_ids: list[str],
    max_items: int = MAX_INDICATORS_PER_REQUEST,
    max_chars: int = MAX_INDICATOR_CHARS,
) -> list[list[str]]:
    """Divide os códigos em lotes que cabem em uma requisição.

    Args:
        indicator_ids: Códigos dos indicadores, na ordem desejada.
        max_items: Máximo de indicadores por lote.
        max_chars: Máximo de caracteres de ``";".join(lote)``.

    Returns:
        Lista de lotes, preservando a ordem original.

    Raises:
        ValueError: Se algum código tiver caracteres inválidos.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for indicator_id in indicator_ids:
        _check_indicator_id(indicator_id)
        added_chars = len(indicator_id) + (1 if current else 0)
        if current and (
            len(current) == max_items or current_chars + added_chars > max_chars
        ):
            chunks.append(current)
            current, current_chars, added_chars = [], 0, len(indicator_id)
        current.append(indicator_id)
        current_chars += added_chars
    if current:
        chunks.append(current)
    return chunks


def _check_indicator_id(indicator_id: str) -> None:
    if not _INDICATOR_ID.match(indicator_id):
        raise ValueError(f"código de indicador inválido: {indicator_id!r}")
