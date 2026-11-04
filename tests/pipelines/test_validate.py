from unittest.mock import MagicMock

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import LoadError, QualityCheckError
from world_bank.pipelines.validate import run_validate
from world_bank.validate.checks import CheckResult

MODULE = "world_bank.pipelines.validate"
WARNING = CheckResult("cobertura", "warning", False, 3, [])
ERROR = CheckResult("faixa", "error", False, 1, [])


@pytest.fixture
def db(mocker: MockerFixture) -> dict[str, MagicMock]:
    mocker.patch(f"{MODULE}.load_checks", return_value=[])
    return {
        "run": mocker.patch(f"{MODULE}.run_checks", return_value=[WARNING]),
        "start": mocker.patch(f"{MODULE}.start_pipeline_run", return_value="exec"),
        "finish": mocker.patch(f"{MODULE}.finish_pipeline_run"),
        "insert": mocker.patch(f"{MODULE}.insert_quality_results"),
    }


def _settings() -> MagicMock:
    return MagicMock(indicators=["AA"])


def test_warnings_finish_with_success_and_are_recorded(
    db: dict[str, MagicMock],
) -> None:
    conn = MagicMock()

    assert run_validate(conn, _settings(), 2000, 2024) == [WARNING]

    db["start"].assert_called_once_with(
        conn, "validate", {"period": "2000:2024", "indicators": ["AA"]}
    )
    db["insert"].assert_called_once_with(conn, "exec", [WARNING])
    db["finish"].assert_called_once_with(conn, "exec", "success", [])


def test_error_rule_fails_and_results_stay_recorded(
    db: dict[str, MagicMock],
) -> None:
    db["run"].return_value = [ERROR]
    conn = MagicMock()

    with pytest.raises(QualityCheckError, match="faixa"):
        run_validate(conn, _settings(), 2000, 2024)

    db["insert"].assert_called_once_with(conn, "exec", [ERROR])
    assert db["finish"].call_args.args[2] == "failed"
    assert "faixa" in db["finish"].call_args.kwargs["error_message"]


def test_database_error_becomes_load_error(db: dict[str, MagicMock]) -> None:
    db["run"].side_effect = psycopg.errors.UndefinedTable("sem tabela")

    with pytest.raises(LoadError, match="sem tabela"):
        run_validate(MagicMock(), _settings(), 2000, 2024)

    assert db["finish"].call_args.args[2] == "failed"
    db["insert"].assert_not_called()
