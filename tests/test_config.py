from pathlib import Path

import pytest

from world_bank.config import load_settings
from world_bank.exceptions import ConfigurationError


def test_load_settings_reads_toml_of_selected_env(config_dir: Path) -> None:
    settings = load_settings("dev", config_dir)

    assert settings.env == "dev"
    assert settings.per_page == 50
    assert settings.indicators == ["SP.POP.TOTL"]
    assert settings.api_base_url == "https://api.worldbank.org/v2"


def test_wb_env_variable_selects_config_file(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (config_dir / "prod.toml").write_text(
        'indicators = ["NY.GDP.PCAP.CD"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("WB_ENV", "prod")

    settings = load_settings(config_dir=config_dir)

    assert settings.env == "prod"
    assert settings.indicators == ["NY.GDP.PCAP.CD"]


def test_environment_variable_overrides_toml(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WB_LOG_LEVEL", "ERROR")

    settings = load_settings("dev", config_dir)

    assert settings.log_level == "ERROR"


def test_database_url_is_secret(config_dir: Path, fake_database_url: str) -> None:
    settings = load_settings("dev", config_dir)

    assert settings.database_url.get_secret_value() == fake_database_url
    assert "fake_pass" not in repr(settings)
    assert "fake_pass" not in str(settings)


def test_database_url_is_read_from_dotenv(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql://from:dotenv@localhost/db\n", encoding="utf-8"
    )

    settings = load_settings("dev", config_dir)

    assert settings.database_url.get_secret_value().endswith("dotenv@localhost/db")


def test_missing_database_url_raises(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_settings("dev", config_dir)


def test_missing_config_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="ausente"):
        load_settings("prod", tmp_path)


def test_invalid_wb_env_raises(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WB_ENV", "staging")

    with pytest.raises(ConfigurationError, match="WB_ENV"):
        load_settings(config_dir=config_dir)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('indicators = ["X"]\nstart_year = 2024\nend_year = 2000\n', "start_year"),
        ("indicators = []\n", "indicators"),
        ('indicators = ["X"]\nper_page = 0\n', "per_page"),
    ],
)
def test_invalid_values_raise(config_dir: Path, content: str, expected: str) -> None:
    (config_dir / "dev.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=expected):
        load_settings("dev", config_dir)


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_project_config_files_are_valid(env: str) -> None:
    settings = load_settings(env)

    assert settings.source_id == 2
    assert len(settings.indicators) == 15
    assert len(set(settings.indicators)) == len(settings.indicators)
