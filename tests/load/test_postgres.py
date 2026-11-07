from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from pydantic import SecretStr
from pytest_mock import MockerFixture

from world_bank.config import load_settings
from world_bank.exceptions import ConfigurationError, LoadError, MigrationError
from world_bank.extract.client import ApiPage
from world_bank.load import postgres
from world_bank.load.postgres import (
    MIGRATIONS_DIR,
    BronzeLoad,
    Migration,
    SourceFile,
    apply_migrations,
    checksum,
    connect,
    content_hash,
    country_codes,
    delete_missing_links,
    finish_pipeline_run,
    insert_pages,
    insert_quality_results,
    insert_source_file,
    json_hash,
    last_successful_bronze_runs,
    latest_payload_hashes,
    latest_source_file,
    list_migrations,
    params_hash,
    read_latest_load,
    read_observation_load,
    request_params,
    start_pipeline_run,
    upsert_rows,
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


def test_read_latest_load_joins_pages_in_order() -> None:
    run_id = uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (run_id, [{"id": "A"}, {"id": "B"}]),
        (run_id, [{"id": "C"}]),
    ]

    load = read_latest_load(conn, "country")

    assert load == BronzeLoad(
        "country", run_id, [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    )
    query = conn.execute.call_args.args[0]
    assert "max(ingested_at)" in query
    assert "order by page" in query
    assert conn.execute.call_args.args[1] == {"endpoint": "country"}


def test_read_latest_load_returns_none_when_never_loaded() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []

    assert read_latest_load(conn, "country") is None


def test_read_latest_load_accepts_page_without_records() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [(uuid4(), None)]

    load = read_latest_load(conn, "country")

    assert load is not None
    assert load.records == []


def _upsert_statements(conn: MagicMock) -> list[str]:
    cursor = conn.cursor.return_value.__enter__.return_value
    return [call.args[0].as_string() for call in cursor.execute.call_args_list]


def test_upsert_rows_skips_database_when_there_are_no_rows() -> None:
    conn = MagicMock()

    assert upsert_rows(conn, "regiao", ["regiao_id"], []) == 0
    conn.cursor.assert_not_called()


def test_upsert_rows_copies_values_in_column_order() -> None:
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    copy = cursor.copy.return_value.__enter__.return_value
    run_id = uuid4()
    rows = [{"regiao_id": "AAA", "nome": "Região", "bronze_run_id": run_id}]

    upsert_rows(conn, "regiao", ["regiao_id"], rows)

    copy.write_row.assert_called_once_with(["AAA", "Região", run_id])


def test_upsert_rows_quotes_names_as_identifiers() -> None:
    conn = MagicMock()
    rows = [{'id"; drop table x; --': "A", "bronze_run_id": uuid4()}]

    upsert_rows(conn, 'tabela"ruim', ['id"; drop table x; --'], rows)

    insert = _upsert_statements(conn)[1]
    assert '"silver"."tabela""ruim"' in insert
    assert '"id""; drop table x; --"' in insert


def test_upsert_rows_only_updates_when_data_columns_change() -> None:
    conn = MagicMock()
    rows = [{"regiao_id": "AAA", "nome": "Região", "bronze_run_id": uuid4()}]

    upsert_rows(conn, "regiao", ["regiao_id"], rows)

    insert = _upsert_statements(conn)[1]
    assert 'on conflict ("regiao_id") do update' in insert
    assert '"bronze_run_id" = excluded."bronze_run_id"' in insert
    assert "atualizado_em = now()" in insert
    # A linhagem fica fora da comparação: conteúdo igual não gera escrita (D-033).
    assert 'where ("alvo"."nome") is distinct from ("excluded"."nome")' in insert


def test_upsert_rows_does_nothing_on_conflict_when_all_columns_are_key() -> None:
    conn = MagicMock()
    rows = [{"indicador_id": "A", "topico_id": 1, "bronze_run_id": uuid4()}]

    upsert_rows(conn, "ponte", ["indicador_id", "topico_id"], rows)

    assert "do nothing" in _upsert_statements(conn)[1]


def test_upsert_rows_returns_rows_written_and_drops_staging() -> None:
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.rowcount = 3
    rows = [{"regiao_id": "AAA", "nome": "Região"}]

    assert upsert_rows(conn, "regiao", ["regiao_id"], rows) == 3
    assert _upsert_statements(conn)[-1] == 'drop table "stg_regiao"'


def test_delete_missing_links_sends_indicators_and_links() -> None:
    conn = MagicMock()
    conn.execute.return_value.rowcount = 2

    deleted = delete_missing_links(conn, ["A", "B"], [("A", 1), ("A", 2)])

    assert deleted == 2
    assert conn.execute.call_args.args[1] == {
        "indicators": ["A", "B"],
        "link_indicators": ["A", "A"],
        "link_topics": [1, 2],
    }


def test_latest_source_file_returns_newest_version() -> None:
    run_id = uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (run_id, b"PK", "abc")

    latest = latest_source_file(conn, "income_history")

    assert latest == SourceFile("income_history", run_id, b"PK", "abc")
    assert "order by ingested_at desc" in conn.execute.call_args.args[0]


def test_latest_source_file_returns_none_when_never_loaded() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    assert latest_source_file(conn, "income_history") is None


def test_insert_source_file_stores_bytes_hash_and_size() -> None:
    conn = MagicMock()
    run_id = uuid4()

    insert_source_file(conn, run_id, "income_history", "https://x.invalid/a", b"PK")

    assert conn.execute.call_args.args[1] == (
        run_id,
        "income_history",
        "https://x.invalid/a",
        b"PK",
        content_hash(b"PK"),
        2,
    )


def test_read_observation_load_filters_endpoint_and_period() -> None:
    run_id = uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        (run_id, [{"id": "A"}]),
        (run_id, None),
    ]

    load = read_observation_load(conn, "country/all/indicator/A", "2000:2024")

    assert load == BronzeLoad("country/all/indicator/A", run_id, [{"id": "A"}])
    query, params = conn.execute.call_args.args
    assert "params ->> 'date' = %(period)s" in query
    assert "max(ingested_at)" in query
    assert params == {"endpoint": "country/all/indicator/A", "period": "2000:2024"}


def test_read_observation_load_returns_none_when_period_is_missing() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []

    assert read_observation_load(conn, "x", "2000:2024") is None


def test_country_codes_maps_iso2_to_iso3() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [("XA", "XAA"), ("1W", "WLD")]

    assert country_codes(conn) == {"XA": "XAA", "1W": "WLD"}


def test_start_pipeline_run_records_running_status() -> None:
    conn = MagicMock()

    run_id = start_pipeline_run(conn, "load-observations", {"period": "2000:2024"})

    query, params = conn.execute.call_args.args
    assert "'running'" in query
    assert params[0] == run_id
    assert params[1] == "load-observations"
    assert params[2].obj == {"period": "2000:2024"}


def test_finish_pipeline_run_records_end_and_counts() -> None:
    conn = MagicMock()
    run_id, bronze_run = uuid4(), uuid4()

    finish_pipeline_run(
        conn, run_id, "failed", [bronze_run], rows_read=2, error_message="erro"
    )

    query, params = conn.execute.call_args.args
    assert "finished_at = now()" in query
    assert "%s::uuid[]" in query
    assert params == ("failed", [bronze_run], 2, None, "erro", run_id)


def test_last_successful_bronze_runs_filters_status_and_params() -> None:
    bronze_run = uuid4()
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = ([bronze_run],)

    assert last_successful_bronze_runs(conn, "cmd", {"a": 1}) == [bronze_run]
    query, params = conn.execute.call_args.args
    assert "status = 'success'" in query
    assert "order by started_at desc" in query
    assert params[0] == "cmd"
    assert params[1].obj == {"a": 1}


def test_last_successful_bronze_runs_returns_none_without_history() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    assert last_successful_bronze_runs(conn, "cmd", {}) is None


def test_insert_quality_results_stores_each_rule() -> None:
    conn = MagicMock()
    run_id = uuid4()
    result = MagicMock(
        severity="warning", passed=False, rows_failed=3, sample=[{"a": 1}]
    )
    result.name = "cobertura"

    insert_quality_results(conn, run_id, [result])

    cursor = conn.cursor.return_value.__enter__.return_value
    rows = cursor.executemany.call_args.args[1]
    assert rows[0][:5] == (run_id, "cobertura", "warning", False, 3)
    assert rows[0][5].obj == [{"a": 1}]


def test_insert_quality_results_skips_empty_list() -> None:
    conn = MagicMock()

    insert_quality_results(conn, uuid4(), [])

    conn.cursor.assert_not_called()


def test_sync_dashboard_password_sem_url_nao_faz_nada(mocker: MockerFixture) -> None:
    conn = mocker.MagicMock()
    settings = mocker.MagicMock(dashboard_database_url=None)

    assert postgres.sync_dashboard_password(conn, settings) is False
    conn.execute.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://outro:segredo@127.0.0.1:5433/world_bank",
        "postgresql://dashboard_leitor@127.0.0.1:5433/world_bank",
    ],
)
def test_sync_dashboard_password_recusa_url_errada(
    mocker: MockerFixture, url: str
) -> None:
    conn = mocker.MagicMock()
    settings = mocker.MagicMock(dashboard_database_url=SecretStr(url))

    with pytest.raises(ConfigurationError, match="dashboard_leitor"):
        postgres.sync_dashboard_password(conn, settings)
    conn.execute.assert_not_called()


def test_sync_dashboard_password_envia_a_senha_criptografada(
    mocker: MockerFixture,
) -> None:
    conn = mocker.MagicMock()
    conn.pgconn.encrypt_password.return_value = b"SCRAM-hash"
    url = "postgresql://dashboard_leitor:s3gredo@127.0.0.1:5433/world_bank"
    settings = mocker.MagicMock(dashboard_database_url=SecretStr(url))

    assert postgres.sync_dashboard_password(conn, settings) is True
    conn.pgconn.encrypt_password.assert_called_once_with(
        b"s3gredo", b"dashboard_leitor", b"scram-sha-256"
    )
    assert "s3gredo" not in repr(conn.execute.call_args)
