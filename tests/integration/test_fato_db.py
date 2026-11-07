"""Testes do fato e do registro de execuções contra o PostgreSQL real.

Ficam fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
As linhas de teste são desfeitas ou apagadas no fim, e nada fica gravado.
"""

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import psycopg
import pytest

from world_bank.exceptions import SchemaValidationError
from world_bank.load.postgres import (
    apply_migrations,
    finish_pipeline_run,
    last_successful_bronze_runs,
    list_migrations,
    start_pipeline_run,
    upsert_rows,
)
from world_bank.pipelines.observations import run_observations

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
KEY = ("pais_iso3", "indicador_id", "ano")


def _database_url() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.removeprefix("DATABASE_URL=").strip()
    pytest.skip("DATABASE_URL não definida no .env")


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_database_url(), autocommit=True) as connection:
        apply_migrations(connection, list_migrations())
        yield connection


@pytest.fixture
def pipeline(conn: psycopg.Connection) -> Iterator[str]:
    """Nome de comando exclusivo do teste; as linhas dele são apagadas no fim."""
    name = f"teste-{uuid4()}"
    yield name
    conn.execute("delete from etl.pipeline_run where pipeline = %s", (name,))


def _dimensions(conn: psycopg.Connection) -> None:
    """Cria um agregado e um indicador de teste, dentro da transação do teste."""
    run_id = uuid4()
    upsert_rows(
        conn,
        "pais",
        ["pais_iso3"],
        [
            {
                "pais_iso3": "T01",
                "pais_iso2": "T1",
                "nome": "Teste",
                "e_agregado": True,
                "tipo_agregado": "outro",
                "bronze_run_id": run_id,
            }
        ],
    )
    upsert_rows(
        conn,
        "fonte",
        ["fonte_id"],
        [
            {
                "fonte_id": -1,
                "codigo": "TESTE",
                "nome": "Teste",
                "conceitos": 0,
                "ultima_atualizacao": "2026-01-31",
                "tem_dados": True,
                "bronze_run_id": run_id,
            }
        ],
    )
    upsert_rows(
        conn,
        "indicador",
        ["indicador_id"],
        [
            {
                "indicador_id": "T.01",
                "nome": "Teste",
                "fonte_id": -1,
                "bronze_run_id": run_id,
            }
        ],
    )


def _row(run_id: UUID, value: Decimal | None = Decimal("1.5")) -> dict[str, Any]:
    return {
        "pais_iso3": "T01",
        "indicador_id": "T.01",
        "ano": 2023,
        "valor": value,
        "casas_decimais": 1,
        "bronze_run_id": run_id,
    }


def _stored(conn: psycopg.Connection) -> tuple[Any, ...] | None:
    return conn.execute(
        "select valor, bronze_run_id from silver.observacao"
        " where pais_iso3 = 'T01' and indicador_id = 'T.01'"
    ).fetchone()


def test_upsert_twice_keeps_row_and_change_updates_it(conn: psycopg.Connection) -> None:
    first, second = uuid4(), uuid4()

    with conn.transaction(force_rollback=True):
        _dimensions(conn)
        assert upsert_rows(conn, "observacao", KEY, [_row(first)]) == 1

        assert upsert_rows(conn, "observacao", KEY, [_row(uuid4())]) == 0
        assert _stored(conn) == (Decimal("1.5"), first)

        changed = [_row(second, Decimal("2.5"))]
        assert upsert_rows(conn, "observacao", KEY, changed) == 1
        assert _stored(conn) == (Decimal("2.5"), second)


def test_null_value_is_accepted_and_does_not_become_zero(
    conn: psycopg.Connection,
) -> None:
    run_id = uuid4()

    with conn.transaction(force_rollback=True):
        _dimensions(conn)
        upsert_rows(conn, "observacao", KEY, [_row(run_id, None)])

        assert _stored(conn) == (None, run_id)


def test_unknown_country_is_rejected(conn: psycopg.Connection) -> None:
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation, match="pais"),
        conn.transaction(),
    ):
        _dimensions(conn)
        unknown = {**_row(uuid4()), "pais_iso3": "NAO"}
        upsert_rows(conn, "observacao", KEY, [unknown])


def test_unknown_indicator_is_rejected(conn: psycopg.Connection) -> None:
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation, match="indicador"),
        conn.transaction(),
    ):
        _dimensions(conn)
        unknown = {**_row(uuid4()), "indicador_id": "NAO.EXISTE"}
        upsert_rows(conn, "observacao", KEY, [unknown])


def test_last_successful_run_ignores_other_status_and_params(
    conn: psycopg.Connection, pipeline: str
) -> None:
    params = {"period": "2000:2024"}
    done, ignored = [uuid4()], [uuid4()]

    assert last_successful_bronze_runs(conn, pipeline, params) is None

    success = start_pipeline_run(conn, pipeline, params)
    finish_pipeline_run(conn, success, "success", done, rows_read=1, rows_written=1)
    failed = start_pipeline_run(conn, pipeline, params)
    finish_pipeline_run(conn, failed, "failed", ignored, error_message="erro")
    other = start_pipeline_run(conn, pipeline, {"period": "2010:2015"})
    finish_pipeline_run(conn, other, "success", ignored, rows_read=1, rows_written=1)

    assert last_successful_bronze_runs(conn, pipeline, params) == done


def test_failure_stays_recorded(conn: psycopg.Connection) -> None:
    indicator = f"T.{uuid4().hex}"
    settings = MagicMock(indicators=[indicator])
    params = json.dumps({"indicators": [indicator]})

    try:
        with pytest.raises(SchemaValidationError, match="rode load-bronze"):
            run_observations(conn, settings, 1900, 1901)

        row = conn.execute(
            "select status, error_message, finished_at is not null"
            " from etl.pipeline_run where params @> %s::jsonb",
            (params,),
        ).fetchone()
        assert row is not None
        assert row[0] == "failed"
        assert "rode load-bronze" in row[1]
        assert row[2] is True
    finally:
        conn.execute(
            "delete from etl.pipeline_run where params @> %s::jsonb", (params,)
        )
