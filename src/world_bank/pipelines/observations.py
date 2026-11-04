"""Pipeline das observações: lê a bronze, transforma e grava o fato da silver.

Não chama a API. Cada execução fica registrada em ``etl.pipeline_run``, inclusive
as que falham (D-046), e é pulada se a bronze não mudou desde a última (D-045).
"""

import logging
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import psycopg

from world_bank.config import Settings
from world_bank.exceptions import LoadError, SchemaValidationError, WorldBankError
from world_bank.extract.endpoints import chunk_indicators
from world_bank.load.postgres import (
    BronzeLoad,
    country_codes,
    finish_pipeline_run,
    last_successful_bronze_runs,
    read_observation_load,
    start_pipeline_run,
    upsert_rows,
)
from world_bank.transform.dimensions import ensure_unique
from world_bank.transform.observations import KEY_COLUMNS, transform_observations

logger = logging.getLogger(__name__)

PIPELINE = "load-observations"
_TABLE = "fato_observacao"


@dataclass(frozen=True)
class ObservationsResult:
    """Resultado de uma execução.

    Attributes:
        status: ``"success"`` se processou, ``"skipped"`` se a bronze não mudou.
        rows_read: Linhas lidas da bronze; ``None`` se a execução foi pulada.
        rows_written: Linhas inseridas ou alteradas; ``None`` se foi pulada.
    """

    status: Literal["success", "skipped"]
    rows_read: int | None
    rows_written: int | None


def read_loads(
    conn: psycopg.Connection, indicators: list[str], period: str
) -> list[BronzeLoad]:
    """Lê a carga mais recente de cada requisição do período (D-044).

    Args:
        conn: Conexão com o banco.
        indicators: Indicadores configurados.
        period: Período no formato da API (ex.: ``"2000:2024"``).

    Returns:
        Uma carga por lote de indicadores, na ordem dos lotes.

    Raises:
        SchemaValidationError: Se faltar alguma carga na bronze.
    """
    loads = []
    for chunk in chunk_indicators(indicators):
        endpoint = f"country/all/indicator/{';'.join(chunk)}"
        load = read_observation_load(conn, endpoint, period)
        if load is None:
            raise SchemaValidationError(
                f"observações de {period} não estão na bronze para {endpoint!r}; "
                "rode load-bronze com esse período"
            )
        loads.append(load)
    return loads


def build_rows(
    loads: list[BronzeLoad], codes: dict[str, str], indicators: list[str]
) -> list[dict]:
    """Transforma as cargas nas linhas do fato, com a linhagem (D-033).

    Args:
        loads: Cargas da bronze.
        codes: Mapa de ``pais_iso2`` para ``pais_iso3``.
        indicators: Indicadores aceitos.

    Returns:
        As linhas prontas para gravar.

    Raises:
        SchemaValidationError: Se algum registro não respeitar as regras.
    """
    rows = [
        {**row, "bronze_run_id": load.run_id}
        for load in loads
        for row in transform_observations(load.records, codes, set(indicators))
    ]
    return ensure_unique(rows, _TABLE, KEY_COLUMNS)


def run_observations(
    conn: psycopg.Connection,
    settings: Settings,
    start_year: int,
    end_year: int,
    full_refresh: bool = False,
) -> ObservationsResult:
    """Executa a carga das observações de ponta a ponta.

    Args:
        conn: Conexão em modo autocommit.
        settings: Configurações (indicadores carregados).
        start_year: Primeiro ano.
        end_year: Último ano.
        full_refresh: Processa de novo mesmo que a bronze não tenha mudado.

    Returns:
        O que foi feito.

    Raises:
        SchemaValidationError: Se faltar dado na bronze ou um registro não
            respeitar as regras. Nada é gravado no fato.
        LoadError: Se o banco recusar a operação. Nada é gravado no fato.
    """
    period = f"{start_year}:{end_year}"
    params = {"period": period, "indicators": settings.indicators}
    run_id = start_pipeline_run(conn, PIPELINE, params)
    bronze_run_ids: list[UUID] = []
    try:
        loads = read_loads(conn, settings.indicators, period)
        bronze_run_ids = [load.run_id for load in loads]
        last_runs = last_successful_bronze_runs(conn, PIPELINE, params)
        if not full_refresh and last_runs == bronze_run_ids:
            finish_pipeline_run(conn, run_id, "skipped", bronze_run_ids)
            logger.info("observations skipped", extra={"period": period})
            return ObservationsResult("skipped", None, None)
        rows = build_rows(loads, country_codes(conn), settings.indicators)
        with conn.transaction():
            written = upsert_rows(conn, _TABLE, KEY_COLUMNS, rows)
    except psycopg.Error as exc:
        error = LoadError(f"falha ao carregar as observações: {exc}")
        finish_pipeline_run(
            conn, run_id, "failed", bronze_run_ids, error_message=str(error)
        )
        raise error from exc
    except WorldBankError as exc:
        finish_pipeline_run(
            conn, run_id, "failed", bronze_run_ids, error_message=str(exc)
        )
        raise
    finish_pipeline_run(
        conn,
        run_id,
        "success",
        bronze_run_ids,
        rows_read=len(rows),
        rows_written=written,
    )
    logger.info(
        "observations loaded",
        extra={"period": period, "rows_read": len(rows), "rows_written": written},
    )
    return ObservationsResult("success", len(rows), written)
