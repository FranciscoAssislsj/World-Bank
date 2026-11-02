from collections.abc import Callable, Iterator
from typing import Any

import pytest

from world_bank.extract.client import WorldBankClient

BASE_URL = "https://api.test/v2"


@pytest.fixture
def base_url() -> str:
    """URL base inventada: nenhuma requisição sai da máquina (respx intercepta)."""
    return BASE_URL


@pytest.fixture
def client() -> Iterator[WorldBankClient]:
    """Cliente com páginas pequenas, 3 tentativas e sem espera entre elas."""
    with WorldBankClient(
        BASE_URL, timeout=1.0, per_page=2, max_retries=3, backoff_seconds=0
    ) as wb_client:
        yield wb_client


@pytest.fixture
def make_payload() -> Callable[..., list[Any]]:
    """Monta uma resposta ``[metadados, registros]`` no formato da API v2."""

    def _make(
        records: list[dict[str, Any]] | None,
        page: int = 1,
        pages: int = 1,
        total: int | None = None,
    ) -> list[Any]:
        metadata = {
            "page": page,
            "pages": pages,
            "per_page": "2",
            "total": total if total is not None else len(records or []),
        }
        return [metadata, records]

    return _make
