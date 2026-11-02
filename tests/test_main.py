import pytest

from world_bank.__main__ import main


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    assert exit_code == 0
    assert "usage: world_bank" in capsys.readouterr().out


def test_main_rejects_unknown_command() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["comando-inexistente"])

    assert exc_info.value.code == 2
