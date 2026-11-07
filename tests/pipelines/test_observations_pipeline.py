from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import LoadError, QualityCheckError, SchemaValidationError
from world_bank.load.postgres import BronzeLoad
from world_bank.pipelines.observations import build_rows, read_loads, run_observations
from world_bank.validate.checks import CheckResult

MODULE = "world_bank.pipelines.observations"
ENDPOINT = "country/all/indicator/AA.BB"
RUN_ID = uuid4()


def _record(year: str = "2023") -> dict[str, Any]:
    return {
        "indicator": {"id": "AA.BB"},
        "country": {"id": "XA"},
        "date": year,
        "value": 1.5,
        "decimal": 1,
    }


def _load(*records: dict[str, Any]) -> BronzeLoad:
    return BronzeLoad(ENDPOINT, RUN_ID, list(records) or [_record()])


@pytest.fixture
def db(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Substitui o acesso ao banco: há uma carga, e nenhuma execução anterior."""
    return {
        "read": mocker.patch(f"{MODULE}.read_observation_load", return_value=_load()),
        "last": mocker.patch(
            f"{MODULE}.last_successful_bronze_runs", return_value=None
        ),
        "codes": mocker.patch(f"{MODULE}.country_codes", return_value={"XA": "XAA"}),
        "start": mocker.patch(f"{MODULE}.start_pipeline_run", return_value="exec"),
        "finish": mocker.patch(f"{MODULE}.finish_pipeline_run"),
        "upsert": mocker.patch(f"{MODULE}.upsert_rows", return_value=1),
    }


@pytest.fixture(autouse=True)
def quality(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Substitui as regras de qualidade: por padrão, nenhuma reprova."""
    return {
        "load": mocker.patch(f"{MODULE}.load_checks", return_value=["regra"]),
        "run": mocker.patch(f"{MODULE}.run_checks", return_value=[]),
        "insert": mocker.patch(f"{MODULE}.insert_quality_results"),
    }


def _settings() -> MagicMock:
    return MagicMock(indicators=["AA.BB"])


def test_read_loads_uses_endpoint_of_each_chunk_and_period(
    db: dict[str, MagicMock],
) -> None:
    conn = MagicMock()

    assert read_loads(conn, ["AA.BB"], "2000:2024") == [db["read"].return_value]
    db["read"].assert_called_once_with(conn, ENDPOINT, "2000:2024")


def test_build_rows_adds_lineage() -> None:
    rows = build_rows([_load()], {"XA": "XAA"}, ["AA.BB"])

    assert rows[0]["pais_iso3"] == "XAA"
    assert rows[0]["bronze_run_id"] == RUN_ID


def test_build_rows_rejects_repeated_key() -> None:
    with pytest.raises(SchemaValidationError, match="chave repetida"):
        build_rows([_load(_record(), _record())], {"XA": "XAA"}, ["AA.BB"])


def test_writes_in_one_transaction_and_records_success(
    db: dict[str, MagicMock],
) -> None:
    conn = MagicMock()

    result = run_observations(conn, _settings(), 2000, 2024)

    assert (result.status, result.rows_read, result.rows_written) == ("success", 1, 1)
    conn.transaction.assert_called_once_with()
    args = db["upsert"].call_args.args
    assert args[1:3] == ("observacao", ("pais_iso3", "indicador_id", "ano"))
    db["start"].assert_called_once_with(
        conn,
        "load-observations",
        {"period": "2000:2024", "indicators": ["AA.BB"]},
    )
    db["finish"].assert_called_once_with(
        conn, "exec", "success", [RUN_ID], rows_read=1, rows_written=1
    )


def test_same_bronze_loads_are_skipped(db: dict[str, MagicMock]) -> None:
    db["last"].return_value = [RUN_ID]
    conn = MagicMock()

    result = run_observations(conn, _settings(), 2000, 2024)

    assert result.status == "skipped"
    db["upsert"].assert_not_called()
    db["finish"].assert_called_once_with(conn, "exec", "skipped", [RUN_ID])


def test_new_bronze_load_is_processed(db: dict[str, MagicMock]) -> None:
    db["last"].return_value = [uuid4()]

    assert run_observations(MagicMock(), _settings(), 2000, 2024).status == "success"
    db["upsert"].assert_called_once()


def test_full_refresh_processes_same_loads(db: dict[str, MagicMock]) -> None:
    db["last"].return_value = [RUN_ID]

    result = run_observations(MagicMock(), _settings(), 2000, 2024, full_refresh=True)

    assert result.status == "success"
    db["upsert"].assert_called_once()


def test_missing_load_records_failure(db: dict[str, MagicMock]) -> None:
    db["read"].return_value = None
    conn = MagicMock()

    with pytest.raises(SchemaValidationError, match="rode load-bronze"):
        run_observations(conn, _settings(), 2000, 2024)

    db["upsert"].assert_not_called()
    args = db["finish"].call_args
    assert args.args[:4] == (conn, "exec", "failed", [])
    assert "rode load-bronze" in args.kwargs["error_message"]


def test_invalid_record_records_failure_with_bronze_runs(
    db: dict[str, MagicMock],
) -> None:
    db["read"].return_value = _load(_record(year="2020Q1"))

    with pytest.raises(SchemaValidationError, match="ano inválido"):
        run_observations(MagicMock(), _settings(), 2000, 2024)

    db["upsert"].assert_not_called()
    assert db["finish"].call_args.args[2:4] == ("failed", [RUN_ID])


def test_database_error_becomes_load_error_and_records_failure(
    db: dict[str, MagicMock],
) -> None:
    db["upsert"].side_effect = psycopg.errors.ForeignKeyViolation("chave inexistente")

    with pytest.raises(LoadError, match="chave inexistente"):
        run_observations(MagicMock(), _settings(), 2000, 2024)

    args = db["finish"].call_args
    assert args.args[2] == "failed"
    assert "chave inexistente" in args.kwargs["error_message"]


def test_rules_run_after_writing_inside_the_transaction(
    db: dict[str, MagicMock], quality: dict[str, MagicMock]
) -> None:
    order = MagicMock()
    conn = order.conn
    order.attach_mock(db["upsert"], "upsert")
    order.attach_mock(quality["run"], "run")

    run_observations(conn, _settings(), 2000, 2024)

    quality["load"].assert_called_once_with("fato")
    names = [call[0] for call in order.mock_calls]
    assert names.index("conn.transaction") < names.index("upsert")
    assert names.index("upsert") < names.index("run")
    assert names.index("run") < names.index("conn.transaction().__exit__")


def test_warnings_do_not_block_and_are_recorded(
    db: dict[str, MagicMock], quality: dict[str, MagicMock]
) -> None:
    warning = CheckResult("regra", "warning", False, 2, [])
    quality["run"].return_value = [warning]
    conn = MagicMock()

    assert run_observations(conn, _settings(), 2000, 2024).status == "success"

    quality["insert"].assert_called_once_with(conn, "exec", [warning])
    assert db["finish"].call_args.args[2] == "success"


def test_error_rule_fails_and_results_stay_recorded(
    db: dict[str, MagicMock], quality: dict[str, MagicMock]
) -> None:
    error = CheckResult("faixa", "error", False, 1, [])
    quality["run"].return_value = [error]
    conn = MagicMock()

    with pytest.raises(QualityCheckError, match="faixa"):
        run_observations(conn, _settings(), 2000, 2024)

    quality["insert"].assert_called_once_with(conn, "exec", [error])
    assert db["finish"].call_args.args[2] == "failed"


def test_skipped_run_does_not_run_rules(
    db: dict[str, MagicMock], quality: dict[str, MagicMock]
) -> None:
    db["last"].return_value = [RUN_ID]

    run_observations(MagicMock(), _settings(), 2000, 2024)

    quality["run"].assert_not_called()
