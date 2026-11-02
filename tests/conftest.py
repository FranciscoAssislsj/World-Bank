"""Fixtures compartilhadas: isolam os testes do ambiente e do .env da máquina."""

from pathlib import Path

import pytest

FAKE_DATABASE_URL = "postgresql://fake_user:fake_pass@localhost:5432/fake_db"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Roda cada teste em um diretório vazio (sem .env) e com variáveis controladas."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WB_ENV", raising=False)
    monkeypatch.delenv("WB_LOG_LEVEL", raising=False)
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)


@pytest.fixture
def fake_database_url() -> str:
    """URL inventada que o ``isolated_env`` coloca em ``DATABASE_URL``."""
    return FAKE_DATABASE_URL


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Diretório de configs inventado, com um dev.toml mínimo."""
    directory = tmp_path / "configs"
    directory.mkdir()
    (directory / "dev.toml").write_text(
        'indicators = ["SP.POP.TOTL"]\nlog_level = "DEBUG"\nper_page = 50\n',
        encoding="utf-8",
    )
    return directory
