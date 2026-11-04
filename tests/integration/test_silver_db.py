"""Testes da silver contra o PostgreSQL real do docker-compose.

Ficam fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
Usam o ``DATABASE_URL`` do ``.env`` da raiz. Cada teste roda numa transação que é
desfeita no fim, então não deixa nada gravado.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest

from world_bank.load.postgres import (
    apply_migrations,
    content_hash,
    delete_missing_links,
    insert_source_file,
    latest_source_file,
    list_migrations,
    upsert_rows,
)

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


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


def _region(run_id: UUID, name: str = "Região Teste") -> dict[str, Any]:
    return {
        "regiao_id": "T01",
        "regiao_iso2": "T1",
        "nome": name,
        "e_geografica": True,
        "bronze_run_id": run_id,
    }


def _region_row(conn: psycopg.Connection) -> tuple[Any, ...] | None:
    return conn.execute(
        "select nome, bronze_run_id from silver.dim_regiao where regiao_id = 'T01'"
    ).fetchone()


def _country(run_id: UUID, **overrides: Any) -> dict[str, Any]:
    row = {
        "pais_iso3": "T01",
        "pais_iso2": "T1",
        "nome": "País Teste",
        "regiao_id": None,
        "nivel_renda_atual_id": None,
        "tipo_emprestimo_atual_id": None,
        "regiao_administrativa_id": None,
        "capital": None,
        "latitude": None,
        "longitude": None,
        "e_agregado": False,
        "tipo_agregado": None,
        "bronze_run_id": run_id,
    }
    return {**row, **overrides}


def test_upsert_twice_keeps_row_and_run_id(conn: psycopg.Connection) -> None:
    first_run = uuid4()

    with conn.transaction(force_rollback=True):
        assert upsert_rows(conn, "dim_regiao", ["regiao_id"], [_region(first_run)]) == 1

        # Mesmo conteúdo vindo de outra carga não é mudança (D-033).
        written = upsert_rows(conn, "dim_regiao", ["regiao_id"], [_region(uuid4())])

        assert written == 0
        assert _region_row(conn) == ("Região Teste", first_run)


def test_upsert_updates_row_when_value_changes(conn: psycopg.Connection) -> None:
    second_run = uuid4()

    with conn.transaction(force_rollback=True):
        upsert_rows(conn, "dim_regiao", ["regiao_id"], [_region(uuid4())])

        written = upsert_rows(
            conn, "dim_regiao", ["regiao_id"], [_region(second_run, "Novo Nome")]
        )

        assert written == 1
        assert _region_row(conn) == ("Novo Nome", second_run)


def test_real_country_without_region_is_rejected(conn: psycopg.Connection) -> None:
    with (
        pytest.raises(psycopg.errors.CheckViolation, match="dim_pais_agregado_ck"),
        conn.transaction(),
    ):
        upsert_rows(conn, "dim_pais", ["pais_iso3"], [_country(uuid4())])


def test_aggregate_with_null_keys_is_accepted(conn: psycopg.Connection) -> None:
    row = _country(uuid4(), e_agregado=True, tipo_agregado="outro")

    with conn.transaction(force_rollback=True):
        assert upsert_rows(conn, "dim_pais", ["pais_iso3"], [row]) == 1


def test_failure_in_last_table_undoes_previous_tables(
    conn: psycopg.Connection,
) -> None:
    link = {"indicador_id": "NAO.EXISTE", "topico_id": -1, "bronze_run_id": uuid4()}

    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        conn.transaction(),
    ):
        upsert_rows(conn, "dim_regiao", ["regiao_id"], [_region(uuid4())])
        upsert_rows(
            conn, "ponte_indicador_topico", ["indicador_id", "topico_id"], [link]
        )

    assert _region_row(conn) is None


def test_links_removed_from_source_are_deleted_and_kept_ones_stay(
    conn: psycopg.Connection,
) -> None:
    run_id = uuid4()
    source = {
        "fonte_id": -1,
        "codigo": "TESTE",
        "nome": "Fonte Teste",
        "conceitos": 0,
        "ultima_atualizacao": "2026-01-31",
        "tem_dados": True,
        "tem_metadados": None,
        "bronze_run_id": run_id,
    }
    indicator = {
        "indicador_id": "T.01",
        "nome": "Indicador Teste",
        "fonte_id": -1,
        "descricao": None,
        "organizacao_fonte": None,
        "bronze_run_id": run_id,
    }
    topics = [
        {"topico_id": topic, "nome": "T", "descricao": None, "bronze_run_id": run_id}
        for topic in (-1, -2)
    ]
    key = ["indicador_id", "topico_id"]
    links = [
        {"indicador_id": "T.01", "topico_id": topic, "bronze_run_id": run_id}
        for topic in (-1, -2)
    ]

    with conn.transaction(force_rollback=True):
        upsert_rows(conn, "dim_fonte", ["fonte_id"], [source])
        upsert_rows(conn, "dim_topico", ["topico_id"], topics)
        upsert_rows(conn, "dim_indicador", ["indicador_id"], [indicator])
        upsert_rows(conn, "ponte_indicador_topico", key, links)

        deleted = delete_missing_links(conn, ["T.01"], [("T.01", -1)])

        remaining = conn.execute(
            "select topico_id, bronze_run_id from silver.ponte_indicador_topico"
            " where indicador_id = 'T.01'"
        ).fetchall()
        assert deleted == 1
        assert remaining == [(-1, run_id)]


def test_source_file_is_append_only_and_keeps_bytes(conn: psycopg.Connection) -> None:
    source = f"teste-{uuid4()}"
    content = b"PK\x00\xff bytes"

    with (
        pytest.raises(psycopg.errors.RaiseException, match="append-only"),
        conn.transaction(),
    ):
        insert_source_file(conn, uuid4(), source, "https://x.invalid/a", content)
        stored = latest_source_file(conn, source)
        assert stored is not None
        assert stored.content == content
        assert stored.content_hash == content_hash(content)
        conn.execute(
            "update bronze.source_file set url = 'x' where source = %s", (source,)
        )

    assert latest_source_file(conn, source) is None


def test_income_classification_requires_known_country(
    conn: psycopg.Connection,
) -> None:
    row = {
        "pais_iso3": "NAO",
        "ano_referencia": 2024,
        "ano_fiscal": 2026,
        "nivel_renda_id": "HIC",
        "bronze_run_id": uuid4(),
    }

    with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
        upsert_rows(
            conn, "classificacao_renda_anual", ["pais_iso3", "ano_referencia"], [row]
        )
