"""Testes contra o PostgreSQL real do docker-compose.

Ficam fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
Usam o ``DATABASE_URL`` do ``.env`` da raiz e não deixam nada gravado.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from world_bank.extract.client import ApiPage
from world_bank.load.postgres import (
    apply_migrations,
    insert_pages,
    latest_payload_hashes,
    list_migrations,
    params_hash,
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
        yield connection


def test_migrate_twice_applies_nothing_the_second_time(
    conn: psycopg.Connection,
) -> None:
    apply_migrations(conn, list_migrations())

    assert apply_migrations(conn, list_migrations()) == []


def test_bronze_rejects_update_and_rolls_back(
    conn: psycopg.Connection, make_api_page: Callable[..., ApiPage]
) -> None:
    apply_migrations(conn, list_migrations())
    page = make_api_page(path=f"teste/{uuid4()}")

    # A transação é desfeita no fim: o teste não deixa linha na bronze.
    with (
        pytest.raises(psycopg.errors.RaiseException, match="append-only"),
        conn.transaction(),
    ):
        insert_pages(conn, uuid4(), [page])
        assert len(latest_payload_hashes(conn, params_hash(page))) == 1
        conn.execute(
            "update bronze.api_response set page = 2 where params_hash = %s",
            (params_hash(page),),
        )

    assert latest_payload_hashes(conn, params_hash(page)) == []
