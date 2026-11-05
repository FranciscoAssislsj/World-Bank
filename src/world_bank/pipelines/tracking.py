"""Registro de uma execução em ``etl.pipeline_run``, com sucesso ou falha (D-046)."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psycopg

from world_bank.exceptions import LoadError, WorldBankError
from world_bank.load.postgres import finish_pipeline_run, start_pipeline_run


@dataclass
class RunStats:
    """Números que a execução informa ao terminar.

    Attributes:
        rows_read: Registros lidos.
        rows_written: Registros gravados.
    """

    rows_read: int | None = None
    rows_written: int | None = None


@contextmanager
def tracked_run(
    conn: psycopg.Connection, pipeline: str, params: dict[str, Any]
) -> Iterator[RunStats]:
    """Abre o registro da execução e o encerra como ``success`` ou ``failed``.

    Args:
        conn: Conexão em modo autocommit, para o registro sobreviver a uma falha.
        pipeline: Nome do comando.
        params: Parâmetros da execução.

    Yields:
        Os números que o bloco preenche para o registro.

    Raises:
        LoadError: Se o banco recusar uma operação fora de ``LoadError``.
        WorldBankError: O erro do bloco, depois de registrado.
    """
    run_id = start_pipeline_run(conn, pipeline, params)
    stats = RunStats()
    try:
        yield stats
    except psycopg.Error as exc:
        error = LoadError(f"falha no banco durante {pipeline}: {exc}")
        finish_pipeline_run(conn, run_id, "failed", [], error_message=str(error))
        raise error from exc
    except WorldBankError as exc:
        finish_pipeline_run(conn, run_id, "failed", [], error_message=str(exc))
        raise
    finish_pipeline_run(
        conn,
        run_id,
        "success",
        [],
        rows_read=stats.rows_read,
        rows_written=stats.rows_written,
    )
