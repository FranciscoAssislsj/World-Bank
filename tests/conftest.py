"""Fixtures compartilhadas: isolam os testes do ambiente e do .env da máquina."""

import json
from collections.abc import Callable, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook

from world_bank.extract.client import ApiPage

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
def make_api_page() -> Callable[..., ApiPage]:
    """Monta uma ``ApiPage`` inventada, como o cliente devolveria."""

    def _make(
        path: str = "country",
        records: list[dict[str, Any]] | None = None,
        page: int = 1,
        pages: int = 1,
        params: dict[str, str] | None = None,
    ) -> ApiPage:
        records = [{"id": "XAA"}] if records is None else records
        metadata = {"page": page, "pages": pages, "total": len(records) * pages}
        return ApiPage(
            path=path,
            params={**(params or {}), "format": "json", "page": str(page)},
            page=page,
            pages=pages,
            total=metadata["total"],
            payload=[metadata, records],
            metadata=metadata,
            records=records,
        )

    return _make


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


@pytest.fixture
def make_income_workbook() -> Callable[..., bytes]:
    """Monta um Excel inventado, no formato do histórico oficial de renda."""

    def _make(
        rows: Sequence[Sequence[Any]],
        fiscal: Sequence[str] = ("FY26", "FY27"),
        years: Sequence[int] = (2024, 2025),
        sheet: str = "Country Analytical History",
        with_header: bool = True,
    ) -> bytes:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = sheet
        worksheet.append([None, "Classificações"])
        if with_header:
            worksheet.append([None, "Bank's fiscal year:", *fiscal])
            worksheet.append([None, "Data for calendar year :", *years])
            worksheet.append([None, "Low income (L)", "<= 1", "<= 2"])
        for row in rows:
            worksheet.append(list(row))
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    return _make
