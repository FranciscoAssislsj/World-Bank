from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import SourceFileError
from world_bank.extract.source_files import download_xlsx
from world_bank.load.postgres import SourceFile, content_hash
from world_bank.pipelines.source_files import run_source_files

URL = "https://exemplo.invalid/arquivo.xlsx"


def _settings() -> MagicMock:
    return MagicMock(income_history_url=URL, request_timeout=5.0)


def _response(content: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=content, request=httpx.Request("GET", URL))


def test_download_returns_file_bytes(mocker: MockerFixture) -> None:
    fake_get = mocker.patch("httpx.get", return_value=_response(b"PK conteudo"))

    assert download_xlsx(URL, 5.0) == b"PK conteudo"
    fake_get.assert_called_once_with(URL, timeout=5.0, follow_redirects=True)


def test_download_fails_on_http_error(mocker: MockerFixture) -> None:
    mocker.patch("httpx.get", return_value=_response(b"", status=404))

    with pytest.raises(SourceFileError, match="falha ao baixar"):
        download_xlsx(URL, 5.0)


def test_download_fails_on_network_error(mocker: MockerFixture) -> None:
    mocker.patch("httpx.get", side_effect=httpx.ConnectError("sem rede"))

    with pytest.raises(SourceFileError, match="sem rede"):
        download_xlsx(URL, 5.0)


def test_download_rejects_response_that_is_not_xlsx(mocker: MockerFixture) -> None:
    mocker.patch("httpx.get", return_value=_response(b"<html>erro</html>"))

    with pytest.raises(SourceFileError, match=r"não é um arquivo \.xlsx"):
        download_xlsx(URL, 5.0)


@pytest.fixture
def fake_db(mocker: MockerFixture) -> dict[str, MagicMock]:
    mocker.patch(
        "world_bank.pipelines.source_files.download_xlsx", return_value=b"PK novo"
    )
    return {
        "latest": mocker.patch("world_bank.pipelines.source_files.latest_source_file"),
        "insert": mocker.patch("world_bank.pipelines.source_files.insert_source_file"),
    }


def test_first_load_inserts_file(fake_db: dict[str, MagicMock]) -> None:
    fake_db["latest"].return_value = None
    conn = MagicMock()

    assert run_source_files(conn, _settings()) == "inserted"
    args = fake_db["insert"].call_args.args
    assert (args[0], args[2], args[3], args[4]) == (
        conn,
        "income_history",
        URL,
        b"PK novo",
    )


def test_same_content_is_not_inserted_again(fake_db: dict[str, MagicMock]) -> None:
    fake_db["latest"].return_value = SourceFile(
        "income_history", uuid4(), b"PK novo", content_hash(b"PK novo")
    )

    assert run_source_files(MagicMock(), _settings()) == "unchanged"
    fake_db["insert"].assert_not_called()


def test_changed_content_is_inserted(fake_db: dict[str, MagicMock]) -> None:
    fake_db["latest"].return_value = SourceFile(
        "income_history", uuid4(), b"PK velho", content_hash(b"PK velho")
    )

    assert run_source_files(MagicMock(), _settings()) == "inserted"
    fake_db["insert"].assert_called_once()
