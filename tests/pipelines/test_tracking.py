from unittest.mock import MagicMock

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import ApiResponseError, LoadError
from world_bank.pipelines.tracking import tracked_run

MODULE = "world_bank.pipelines.tracking"


@pytest.fixture
def db(mocker: MockerFixture) -> dict[str, MagicMock]:
    return {
        "start": mocker.patch(f"{MODULE}.start_pipeline_run", return_value="exec"),
        "finish": mocker.patch(f"{MODULE}.finish_pipeline_run"),
    }


def test_success_records_the_numbers(db: dict[str, MagicMock]) -> None:
    conn = MagicMock()

    with tracked_run(conn, "comando", {"a": 1}) as stats:
        stats.rows_read = 3
        stats.rows_written = 2

    db["start"].assert_called_once_with(conn, "comando", {"a": 1})
    db["finish"].assert_called_once_with(
        conn, "exec", "success", [], rows_read=3, rows_written=2
    )


def test_pipeline_error_is_recorded_and_raised_again(
    db: dict[str, MagicMock],
) -> None:
    conn = MagicMock()

    with pytest.raises(ApiResponseError), tracked_run(conn, "comando", {}):
        raise ApiResponseError("API fora do ar")

    db["finish"].assert_called_once_with(
        conn, "exec", "failed", [], error_message="API fora do ar"
    )


def test_database_error_becomes_load_error(db: dict[str, MagicMock]) -> None:
    conn = MagicMock()

    with (
        pytest.raises(LoadError, match="durante comando"),
        tracked_run(conn, "comando", {}),
    ):
        raise psycopg.errors.UndefinedTable("sem tabela")

    assert db["finish"].call_args.args[2] == "failed"
