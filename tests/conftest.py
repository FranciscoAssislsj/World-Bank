"""Fixtures compartilhadas: isolam os testes do ambiente e do .env da máquina."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
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
def load_fixture() -> Callable[[str], Any]:
    """Lê um JSON inventado de ``tests/fixtures/``."""

    def _load(name: str) -> Any:
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    return _load


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
