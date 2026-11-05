from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import ConfigurationError, LoadError
from world_bank.pipelines.gold import run_gold

MODULE = "world_bank.pipelines.gold"
TRACKING = "world_bank.pipelines.tracking"


@pytest.fixture
def db(mocker: MockerFixture) -> dict[str, MagicMock]:
    return {
        "load": mocker.patch(f"{MODULE}.load_views", return_value=["view"]),
        "rebuild": mocker.patch(
            f"{MODULE}.rebuild_views", return_value={"a": 2, "b": 3}
        ),
        "removed": mocker.patch(f"{MODULE}.count_flagged_values", return_value=29),
        "start": mocker.patch(f"{TRACKING}.start_pipeline_run", return_value="exec"),
        "finish": mocker.patch(f"{TRACKING}.finish_pipeline_run"),
    }


def test_success_records_total_rows(db: dict[str, MagicMock]) -> None:
    conn = MagicMock()

    assert run_gold(conn) == {"a": 2, "b": 3}

    db["start"].assert_called_once_with(conn, "build-gold", {})
    db["rebuild"].assert_called_once_with(conn, ["view"])
    db["finish"].assert_called_once_with(
        conn, "exec", "success", [], rows_read=None, rows_written=5
    )


def test_flagged_values_are_logged_as_warning(
    db: dict[str, MagicMock], caplog: pytest.LogCaptureFixture
) -> None:
    run_gold(MagicMock())

    assert "values flagged as unusual" in caplog.text


def test_no_flagged_values_logs_no_warning(
    db: dict[str, MagicMock], caplog: pytest.LogCaptureFixture
) -> None:
    db["removed"].return_value = 0

    run_gold(MagicMock())

    assert "values flagged as unusual" not in caplog.text


def test_invalid_file_fails_before_rebuilding(db: dict[str, MagicMock]) -> None:
    db["load"].side_effect = ConfigurationError("cabeçalho sem Chave")

    with pytest.raises(ConfigurationError):
        run_gold(MagicMock())

    db["rebuild"].assert_not_called()
    assert db["finish"].call_args.args[2] == "failed"


def test_load_failure_is_recorded(db: dict[str, MagicMock]) -> None:
    db["rebuild"].side_effect = LoadError("views da gold vazias")

    with pytest.raises(LoadError):
        run_gold(MagicMock())

    assert db["finish"].call_args.args[2] == "failed"
    assert "vazias" in db["finish"].call_args.kwargs["error_message"]
