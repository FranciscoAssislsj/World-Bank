"""Pipeline das dimensões: lê a bronze, transforma e grava a silver.

Não chama a API: tudo vem da carga mais recente de cada endpoint na bronze (D-013).
As 9 tabelas são gravadas numa única transação (D-019).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg

from world_bank.config import Settings
from world_bank.exceptions import LoadError, SchemaValidationError
from world_bank.extract.endpoints import DIMENSION_PATHS
from world_bank.load.postgres import (
    BronzeLoad,
    SourceFile,
    delete_missing_links,
    latest_source_file,
    read_latest_load,
    upsert_rows,
)
from world_bank.pipelines.source_files import INCOME_HISTORY_SOURCE
from world_bank.transform.dimensions import (
    Record,
    Row,
    ensure_unique,
    transform_countries,
    transform_income_levels,
    transform_indicator_topics,
    transform_indicators,
    transform_lending_types,
    transform_regions,
    transform_sources,
    transform_topics,
)
from world_bank.transform.income_history import transform_income_history

logger = logging.getLogger(__name__)

_LINKS_TABLE = "indicador_topico"


@dataclass(frozen=True)
class TableRows:
    """Linhas prontas para gravar em uma tabela da silver.

    Attributes:
        table: Nome da tabela.
        key_columns: Colunas da chave primária.
        rows: Linhas, com as colunas de dado e a linhagem.
    """

    table: str
    key_columns: tuple[str, ...]
    rows: list[Row]


@dataclass(frozen=True)
class TableResult:
    """Resultado da gravação de uma tabela.

    Attributes:
        table: Nome da tabela.
        rows_read: Linhas vindas da bronze.
        rows_written: Linhas inseridas ou alteradas.
    """

    table: str
    rows_read: int
    rows_written: int


def build_tables(
    catalogs: dict[str, BronzeLoad],
    indicators: list[BronzeLoad],
    income_history: SourceFile,
) -> list[TableRows]:
    """Transforma as cargas da bronze nas 9 tabelas, na ordem de gravação.

    A ordem respeita as chaves estrangeiras: uma tabela vem depois das que ela
    referencia.

    Args:
        catalogs: Carga de cada cadastro, pela chave de ``DIMENSION_PATHS``.
        indicators: Uma carga por indicador configurado.
        income_history: Arquivo do histórico oficial de renda.

    Returns:
        As tabelas prontas para gravar.

    Raises:
        SchemaValidationError: Se algum registro não respeitar as regras.
    """
    regions = _rows(catalogs["region"], transform_regions)
    income_levels = _rows(catalogs["income_level"], transform_income_levels)
    lending_types = _rows(catalogs["lending_type"], transform_lending_types)
    countries = _with_run_id(
        transform_countries(
            catalogs["country"].records,
            [row["regiao_id"] for row in regions],
            [row["nivel_renda_id"] for row in income_levels],
            [row["tipo_emprestimo_id"] for row in lending_types],
        ),
        catalogs["country"].run_id,
    )
    real_countries = [row["pais_iso3"] for row in countries if not row["e_agregado"]]
    income_rows = _with_run_id(
        transform_income_history(income_history.content, real_countries),
        income_history.run_id,
    )
    indicator_rows = [
        row for load in indicators for row in _rows(load, transform_indicators)
    ]
    link_rows = [
        row for load in indicators for row in _rows(load, transform_indicator_topics)
    ]
    ensure_unique(indicator_rows, "indicador", ["indicador_id"])
    ensure_unique(link_rows, _LINKS_TABLE, ["indicador_id", "topico_id"])
    return [
        TableRows("regiao", ("regiao_id",), regions),
        TableRows("nivel_renda", ("nivel_renda_id",), income_levels),
        TableRows("tipo_emprestimo", ("tipo_emprestimo_id",), lending_types),
        TableRows("fonte", ("fonte_id",), _rows(catalogs["source"], transform_sources)),
        TableRows("topico", ("topico_id",), _rows(catalogs["topic"], transform_topics)),
        TableRows("pais", ("pais_iso3",), countries),
        TableRows(
            "classificacao_renda_anual", ("pais_iso3", "ano_referencia"), income_rows
        ),
        TableRows("indicador", ("indicador_id",), indicator_rows),
        TableRows(_LINKS_TABLE, ("indicador_id", "topico_id"), link_rows),
    ]


def write_tables(
    conn: psycopg.Connection, tables: list[TableRows], indicator_ids: list[str]
) -> list[TableResult]:
    """Grava as tabelas numa única transação (D-019).

    Args:
        conn: Conexão em modo autocommit.
        tables: Tabelas na ordem de gravação.
        indicator_ids: Indicadores carregados, para sincronizar a ponte (D-030).

    Returns:
        O resultado de cada tabela.

    Raises:
        LoadError: Se o banco recusar a gravação. Nada fica gravado.
    """
    results = []
    try:
        with conn.transaction():
            for table in tables:
                written = upsert_rows(conn, table.table, table.key_columns, table.rows)
                if table.table == _LINKS_TABLE:
                    links = [
                        (row["indicador_id"], row["topico_id"]) for row in table.rows
                    ]
                    written += delete_missing_links(conn, indicator_ids, links)
                results.append(TableResult(table.table, len(table.rows), written))
    except psycopg.Error as exc:
        raise LoadError(f"falha ao gravar as dimensões da silver: {exc}") from exc
    return results


def run_dimensions(conn: psycopg.Connection, settings: Settings) -> list[TableResult]:
    """Executa a carga das dimensões de ponta a ponta.

    Args:
        conn: Conexão em modo autocommit.
        settings: Configurações (indicadores carregados).

    Returns:
        O resultado de cada tabela, na ordem de gravação.

    Raises:
        SchemaValidationError: Se faltar um endpoint na bronze ou um registro não
            respeitar as regras. Nada é gravado.
        LoadError: Se o banco recusar a gravação. Nada fica gravado.
    """
    catalogs = {
        name: _read(conn, endpoint) for name, endpoint in DIMENSION_PATHS.items()
    }
    indicators = [
        _read(conn, f"indicator/{indicator_id}") for indicator_id in settings.indicators
    ]
    results = write_tables(
        conn,
        build_tables(catalogs, indicators, _read_income_history(conn)),
        settings.indicators,
    )
    for result in results:
        logger.info(
            "silver table loaded",
            extra={
                "table": result.table,
                "rows_read": result.rows_read,
                "rows_written": result.rows_written,
            },
        )
    return results


def _read_income_history(conn: psycopg.Connection) -> SourceFile:
    income_history = latest_source_file(conn, INCOME_HISTORY_SOURCE)
    if income_history is None:
        raise SchemaValidationError(
            "histórico de renda não está na bronze; rode load-bronze antes"
        )
    return income_history


def _read(conn: psycopg.Connection, endpoint: str) -> BronzeLoad:
    load = read_latest_load(conn, endpoint)
    if load is None:
        raise SchemaValidationError(
            f"endpoint {endpoint!r} não está na bronze; rode load-bronze antes"
        )
    return load


def _rows(
    load: BronzeLoad, transform: Callable[[list[Record]], list[Row]]
) -> list[Row]:
    return _with_run_id(transform(load.records), load.run_id)


def _with_run_id(rows: list[Row], run_id: UUID) -> list[dict[str, Any]]:
    """Acrescenta a linhagem (D-033) às linhas transformadas."""
    return [{**row, "bronze_run_id": run_id} for row in rows]
