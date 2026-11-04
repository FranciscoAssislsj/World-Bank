from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from world_bank.__main__ import main
from world_bank.exceptions import LoadError


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    assert exit_code == 0
    assert "usage: world_bank" in capsys.readouterr().out


def test_main_migrate_applies_project_migrations(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_apply = mocker.patch("world_bank.__main__.apply_migrations", return_value=[])

    exit_code = main(["migrate"])

    assert exit_code == 0
    conn = fake_connect.return_value.__enter__.return_value
    applied_files = [m.filename for m in fake_apply.call_args.args[1]]
    assert fake_apply.call_args.args[0] is conn
    assert "001_schemas.sql" in applied_files


def test_main_returns_1_when_command_fails(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch(
        "world_bank.__main__.connect", side_effect=LoadError("banco desligado")
    )

    assert main(["migrate"]) == 1


def _settings(mocker: MockerFixture) -> MagicMock:
    settings = mocker.MagicMock()
    settings.log_level = "INFO"
    settings.env = "dev"
    return settings


def test_main_rejects_unknown_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["comando-inexistente"])

    assert exc_info.value.code == 2


def test_main_load_bronze_uses_config_years_by_default(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    mocker.patch("world_bank.__main__.WorldBankClient")
    mocker.patch("world_bank.__main__.connect")
    mocker.patch("world_bank.__main__.run_source_files")
    fake_run = mocker.patch("world_bank.__main__.run_bronze", return_value=[])

    assert main(["load-bronze"]) == 0
    assert fake_run.call_args.args[3:] == (2000, 2024)


def test_main_load_bronze_accepts_year_range(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.WorldBankClient")
    mocker.patch("world_bank.__main__.run_source_files")
    mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_bronze", return_value=[])

    assert main(["load-bronze", "--start", "2010", "--end", "2015"]) == 0
    assert fake_run.call_args.args[3:] == (2010, 2015)


def test_main_load_dimensions_runs_pipeline(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_dimensions", return_value=[])

    exit_code = main(["load-dimensions"])

    assert exit_code == 0
    conn = fake_connect.return_value.__enter__.return_value
    fake_run.assert_called_once_with(conn, settings)


def test_main_load_dimensions_returns_1_when_load_fails(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.connect")
    mocker.patch(
        "world_bank.__main__.run_dimensions", side_effect=LoadError("chave inválida")
    )

    assert main(["load-dimensions"]) == 1


def test_main_load_bronze_also_stores_income_history(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    mocker.patch("world_bank.__main__.WorldBankClient")
    fake_connect = mocker.patch("world_bank.__main__.connect")
    mocker.patch("world_bank.__main__.run_bronze", return_value=[])
    fake_files = mocker.patch("world_bank.__main__.run_source_files")

    assert main(["load-bronze"]) == 0

    conn = fake_connect.return_value.__enter__.return_value
    fake_files.assert_called_once_with(conn, settings)
