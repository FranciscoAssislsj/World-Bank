from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.config import load_settings
from world_bank.exceptions import LoadError, MigrationError
from world_bank.extract.client import ApiPage
from world_bank.load.postgres import (
    MIGRATIONS_DIR,
    Migration,
    apply_migrations,
    checksum,
    connect,
    insert_pages,
    json_hash,
    latest_payload_hashes,
    list_migrations,
    params_hash,
    request_params,
)


def _write(directory: Path, name: str, sql: str = "select 1;") -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def _migration(version: str, sql: str = "select 1;") -> Migration:
    return Migration(version, f"{version}_teste.sql", sql, checksum(sql))


def _fake_conn(applied: list[tuple[str, str]]) -> MagicMock:
    """Conexão falsa cuja etl.schema_migrations já contém ``applied``."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = applied
    return conn


def _executed_sql(conn: MagicMock) -> list[str]:
    return [call.args[0] for call in conn.execute.call_args_list]


def test_checksum_ignores_line_ending_style() -> None:
    assert checksum("select 1;\r\nselect 2;\r\n") == checksum("select 1;\nselect 2;\n")


def test_checksum_changes_when_content_changes() -> None:
    assert checksum("select 1;") != checksum("select 2;")


def test_list_migrations_orders_by_version(tmp_path: Path) -> None:
    _write(tmp_path, "010_dez.sql")
    _write(tmp_path, "002_dois.sql", "create schema b;")
    _write(tmp_path, "001_um.sql")

    migrations = list_migrations(tmp_path)

    assert [m.filename for m in migrations] == [
        "001_um.sql",
        "002_dois.sql",
        "010_dez.sql",
    ]
    assert migrations[1].version == "002"
    assert migrations[1].sql == "create schema b;"
    assert migrations[1].checksum == checksum("create schema b;")


@pytest.mark.parametrize("name", ["1_curto.sql", "001-hifen.sql", "001_Maiuscula.sql"])
def test_list_migrations_rejects_bad_names(tmp_path: Path, name: str) -> None:
    _write(tmp_path, name)

    with pytest.raises(MigrationError, match="fora do padrão"):
        list_migrations(tmp_path)


def test_list_migrations_rejects_repeated_version(tmp_path: Path) -> None:
    _write(tmp_path, "001_a.sql")
    _write(tmp_path, "001_b.sql")

    with pytest.raises(MigrationError, match="repetida"):
        list_migrations(tmp_path)


def test_project_migrations_are_valid() -> None:
    migrations = list_migrations(MIGRATIONS_DIR)

    assert [m.filename for m in migrations][:2] == ["001_schemas.sql", "002_bronze.sql"]


def test_apply_migrations_runs_only_pending_in_order() -> None:
    first, second, third = (
        _migration("001"),
        _migration("002", "b"),
        _migration("003", "c"),
    )
    conn = _fake_conn(applied=[("001", first.checksum)])

    applied = apply_migrations(conn, [first, second, third])

    assert applied == [second, third]
    bootstrap, read_applied, *rest = _executed_sql(conn)
    assert "create table if not exists etl.schema_migrations" in bootstrap
    assert read_applied.startswith("select version, checksum")
    # Cada migração pendente roda e logo depois é registrada.
    assert rest[0::2] == ["b", "c"]
    assert all(
        sql.startswith("insert into etl.schema_migrations") for sql in rest[1::2]
    )
    assert conn.execute.call_args_list[3].args[1] == (
        "002",
        second.filename,
        second.checksum,
    )


def test_apply_migrations_does_nothing_when_all_applied() -> None:
    first = _migration("001")
    conn = _fake_conn(applied=[("001", first.checksum)])

    assert apply_migrations(conn, [first]) == []
    assert len(_executed_sql(conn)) == 2  # só a preparação e a leitura do registro


def test_apply_migrations_rejects_edited_migration_before_applying_any() -> None:
    first, second = _migration("001", "editada"), _migration("002")
    conn = _fake_conn(applied=[("001", checksum("original"))])

    with pytest.raises(MigrationError, match=r"001_teste\.sql foi alterada"):
        apply_migrations(conn, [first, second])
    assert second.sql not in _executed_sql(conn)[2:]


def test_apply_migrations_wraps_sql_errors() -> None:
    broken = _migration("001", "create tabel x;")
    conn = _fake_conn(applied=[])
    conn.execute.side_effect = [
        MagicMock(),
        conn.execute.return_value,
        psycopg.errors.SyntaxError("erro de sintaxe"),
    ]

    with pytest.raises(MigrationError, match=r"falha ao aplicar 001_teste\.sql"):
        apply_migrations(conn, [broken])


def test_connect_wraps_connection_errors(
    mocker: MockerFixture, config_dir: Path
) -> None:
    mocker.patch(
        "world_bank.load.postgres.psycopg.connect",
        side_effect=psycopg.OperationalError("connection refused"),
    )

    with pytest.raises(LoadError, match="não foi possível conectar"):
        connect(load_settings(config_dir=config_dir))


def test_connect_uses_database_url_in_autocommit(
    mocker: MockerFixture, config_dir: Path, fake_database_url: str
) -> None:
    fake_connect = mocker.patch("world_bank.load.postgres.psycopg.connect")

    connect(load_settings(config_dir=config_dir))

    fake_connect.assert_called_once_with(fake_database_url, autocommit=True)


def test_json_hash_ignores_key_order() -> None:
    assert json_hash({"a": 1, "b": [1, 2]}) == json_hash({"b": [1, 2], "a": 1})


def test_json_hash_changes_when_a_value_changes() -> None:
    assert json_hash([{"page": 1}, [{"value": 10}]]) != json_hash(
        [{"page": 1}, [{"value": 11}]]
    )


def test_params_hash_ignores_page_and_key_order(
    make_api_page: Callable[..., ApiPage],
) -> None:
    first = make_api_page(page=1, pages=2, params={"date": "2000:2024", "source": "2"})
    second = make_api_page(page=2, pages=2, params={"source": "2", "date": "2000:2024"})

    assert params_hash(first) == params_hash(second)
    assert "page" not in request_params(first)


def test_params_hash_changes_with_endpoint_or_params(
    make_api_page: Callable[..., ApiPage],
) -> None:
    base = make_api_page(params={"date": "2000:2024"})

    assert params_hash(base) != params_hash(make_api_page(params={"date": "2000:2023"}))
    assert params_hash(base) != params_hash(
        make_api_page(path="region", params={"date": "2000:2024"})
    )


def test_latest_payload_hashes_returns_hashes_in_page_order() -> None:
    conn = _fake_conn(applied=[("h1",), ("h2",)])

    assert latest_payload_hashes(conn, "req") == ["h1", "h2"]
    sql, params = conn.execute.call_args.args
    assert "max(ingested_at)" in sql
    assert "order by page" in sql
    assert params == {"hash": "req"}


def test_insert_pages_keeps_original_payload(
    make_api_page: Callable[..., ApiPage],
    load_fixture: Callable[[str], Any],
) -> None:
    payload = load_fixture("observations_page.json")
    page = make_api_page(path="country/all/indicator/SP.POP.TOTL", records=payload[1])
    page = replace(page, payload=payload, total=2)
    conn = MagicMock()
    run_id = uuid4()

    insert_pages(conn, run_id, [page])

    cursor = conn.cursor.return_value.__enter__.return_value
    sql, rows = cursor.executemany.call_args.args
    assert sql.strip().startswith("insert into bronze.api_response")
    (row,) = rows
    assert row[0] == run_id
    assert row[1] == "country/all/indicator/SP.POP.TOTL"
    assert row[2].obj == request_params(page)
    assert row[3] == params_hash(page)
    assert row[4:8] == (1, 1, 2, 2)
    assert row[8].obj == payload
    assert row[9] == json_hash(payload)
