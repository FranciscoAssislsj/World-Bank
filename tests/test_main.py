from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from world_bank.__main__ import main
from world_bank.exceptions import LoadError, QualityCheckError


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


def test_main_load_observations_uses_config_years_by_default(
    mocker: MockerFixture,
) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_observations")

    assert main(["load-observations"]) == 0

    conn = fake_connect.return_value.__enter__.return_value
    fake_run.assert_called_once_with(conn, settings, 2000, 2024, False)


def test_main_load_observations_passes_options(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_observations")

    args = ["load-observations", "--start", "2010", "--end", "2015", "--full-refresh"]
    assert main(args) == 0

    conn = fake_connect.return_value.__enter__.return_value
    fake_run.assert_called_once_with(conn, settings, 2010, 2015, True)


def test_main_load_observations_returns_1_when_load_fails(
    mocker: MockerFixture,
) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.connect")
    mocker.patch(
        "world_bank.__main__.run_observations", side_effect=LoadError("chave inválida")
    )

    assert main(["load-observations"]) == 1


def test_main_validate_uses_config_years_by_default(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_validate", return_value=[])

    assert main(["validate"]) == 0

    conn = fake_connect.return_value.__enter__.return_value
    fake_run.assert_called_once_with(conn, settings, 2000, 2024)


def test_main_validate_passes_period(mocker: MockerFixture) -> None:
    settings = _settings(mocker)
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_run = mocker.patch("world_bank.__main__.run_validate", return_value=[])

    assert main(["validate", "--start", "2010", "--end", "2015"]) == 0

    conn = fake_connect.return_value.__enter__.return_value
    fake_run.assert_called_once_with(conn, settings, 2010, 2015)


def test_main_validate_returns_1_when_error_rule_fails(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.connect")
    mocker.patch(
        "world_bank.__main__.run_validate",
        side_effect=QualityCheckError("faixa_percentual (1)"),
    )

    assert main(["validate"]) == 1


def test_main_build_gold_runs_pipeline(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    fake_connect = mocker.patch("world_bank.__main__.connect")
    fake_gold = mocker.patch("world_bank.__main__.run_gold")

    assert main(["build-gold"]) == 0

    fake_gold.assert_called_once_with(fake_connect.return_value.__enter__.return_value)


def test_main_build_gold_returns_1_when_it_fails(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.connect")
    mocker.patch("world_bank.__main__.run_gold", side_effect=LoadError("vazia"))

    assert main(["build-gold"]) == 1


def _patch_steps(mocker: MockerFixture) -> tuple[MagicMock, dict[str, MagicMock]]:
    """Troca cada passo do run-all por um falso que anota a ordem das chamadas."""
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    manager = MagicMock()
    names = [
        "run_migrate",
        "run_load_bronze",
        "run_load_dimensions",
        "run_load_observations",
        "run_validate_command",
        "run_build_gold",
    ]
    steps = {}
    for name in names:
        steps[name] = mocker.patch(f"world_bank.__main__.{name}")
        manager.attach_mock(steps[name], name)
    return manager, steps


def test_main_run_all_runs_steps_in_order_and_validates_before_gold(
    mocker: MockerFixture,
) -> None:
    manager, _ = _patch_steps(mocker)

    assert main(["run-all"]) == 0

    assert [call[0] for call in manager.mock_calls] == [
        "run_migrate",
        "run_load_bronze",
        "run_load_dimensions",
        "run_load_observations",
        "run_validate_command",
        "run_build_gold",
    ]


def test_main_run_all_passes_options(mocker: MockerFixture) -> None:
    _, steps = _patch_steps(mocker)

    main(["run-all", "--start", "2010", "--end", "2020", "--full-refresh"])

    assert steps["run_load_bronze"].call_args.args[1:] == (2010, 2020)
    assert steps["run_load_observations"].call_args.args[1:] == (2010, 2020, True)
    assert steps["run_validate_command"].call_args.args[1:] == (2010, 2020)


def test_main_run_all_stops_at_the_first_failure(mocker: MockerFixture) -> None:
    _, steps = _patch_steps(mocker)
    steps["run_validate_command"].side_effect = QualityCheckError("faixa (1)")

    assert main(["run-all"]) == 1

    steps["run_build_gold"].assert_not_called()


def test_load_dimensions_records_the_run(mocker: MockerFixture) -> None:
    mocker.patch("world_bank.__main__.load_settings", return_value=_settings(mocker))
    mocker.patch("world_bank.__main__.connect")
    result = MagicMock(rows_read=5, rows_written=2)
    mocker.patch("world_bank.__main__.run_dimensions", return_value=[result])
    mocker.patch(
        "world_bank.pipelines.tracking.start_pipeline_run", return_value="exec"
    )
    finish = mocker.patch("world_bank.pipelines.tracking.finish_pipeline_run")

    assert main(["load-dimensions"]) == 0

    assert finish.call_args.args[1:] == ("exec", "success", [])
    assert finish.call_args.kwargs == {"rows_read": 5, "rows_written": 2}


def test_load_bronze_records_the_run_and_only_counts_what_was_inserted(
    mocker: MockerFixture,
) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    mocker.patch("world_bank.__main__.connect")
    mocker.patch("world_bank.__main__.WorldBankClient")
    mocker.patch("world_bank.__main__.run_source_files")
    results = [
        MagicMock(records=10, status="inserted"),
        MagicMock(records=7, status="unchanged"),
    ]
    mocker.patch("world_bank.__main__.run_bronze", return_value=results)
    start = mocker.patch(
        "world_bank.pipelines.tracking.start_pipeline_run", return_value="exec"
    )
    finish = mocker.patch("world_bank.pipelines.tracking.finish_pipeline_run")

    assert main(["load-bronze"]) == 0

    assert start.call_args.args[1:] == ("load-bronze", {"period": "2000:2024"})
    assert finish.call_args.kwargs == {"rows_read": 17, "rows_written": 10}


def test_load_bronze_records_failure_when_the_income_file_fails(
    mocker: MockerFixture,
) -> None:
    settings = _settings(mocker)
    settings.start_year, settings.end_year = 2000, 2024
    mocker.patch("world_bank.__main__.load_settings", return_value=settings)
    mocker.patch("world_bank.__main__.connect")
    mocker.patch("world_bank.__main__.WorldBankClient")
    mocker.patch("world_bank.__main__.run_bronze", return_value=[])
    mocker.patch(
        "world_bank.__main__.run_source_files", side_effect=LoadError("sem arquivo")
    )
    mocker.patch(
        "world_bank.pipelines.tracking.start_pipeline_run", return_value="exec"
    )
    finish = mocker.patch("world_bank.pipelines.tracking.finish_pipeline_run")

    assert main(["load-bronze"]) == 1

    assert finish.call_args.args[2] == "failed"
