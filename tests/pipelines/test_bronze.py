from collections.abc import Callable, Iterator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from world_bank.config import Settings
from world_bank.exceptions import ApiResponseError
from world_bank.extract.client import ApiPage
from world_bank.load.postgres import json_hash, params_hash
from world_bank.pipelines.bronze import group_by_request, load_request, run_bronze

MakePage = Callable[..., ApiPage]


@pytest.fixture
def fake_db(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Substitui a leitura e a gravação na bronze por mocks."""
    return {
        "latest": mocker.patch(
            "world_bank.pipelines.bronze.latest_payload_hashes", return_value=[]
        ),
        "insert": mocker.patch("world_bank.pipelines.bronze.insert_pages"),
    }


def _two_pages(make_api_page: MakePage) -> list[ApiPage]:
    return [
        make_api_page(records=[{"id": "A"}, {"id": "B"}], page=1, pages=2),
        make_api_page(records=[{"id": "C"}], page=2, pages=2),
    ]


def test_load_request_inserts_when_never_loaded(
    make_api_page: MakePage, fake_db: dict[str, MagicMock]
) -> None:
    pages = _two_pages(make_api_page)
    conn, run_id = MagicMock(), uuid4()

    result = load_request(conn, run_id, pages)

    fake_db["insert"].assert_called_once_with(conn, run_id, pages)
    assert result.status == "inserted"
    assert (result.endpoint, result.pages, result.records) == ("country", 2, 3)
    assert result.params_hash == params_hash(pages[0])


def test_load_request_skips_when_same_as_latest(
    make_api_page: MakePage, fake_db: dict[str, MagicMock]
) -> None:
    pages = _two_pages(make_api_page)
    fake_db["latest"].return_value = [json_hash(page.payload) for page in pages]

    result = load_request(MagicMock(), uuid4(), pages)

    fake_db["insert"].assert_not_called()
    assert result.status == "unchanged"


@pytest.mark.parametrize("change", ["segunda-pagina-mudou", "pagina-a-menos"])
def test_load_request_inserts_all_pages_when_anything_changed(
    make_api_page: MakePage, fake_db: dict[str, MagicMock], change: str
) -> None:
    pages = _two_pages(make_api_page)
    first_hash = json_hash(pages[0].payload)
    stored = [first_hash, "outro"] if change == "segunda-pagina-mudou" else [first_hash]
    fake_db["latest"].return_value = stored

    result = load_request(MagicMock(), uuid4(), pages)

    assert fake_db["insert"].call_args.args[2] == pages
    assert result.status == "inserted"


def test_group_by_request_splits_consecutive_requests(make_api_page: MakePage) -> None:
    region = make_api_page(path="region")
    country = _two_pages(make_api_page)

    groups = list(group_by_request([region, *country]))

    assert groups == [[region], country]


def test_group_by_request_raises_before_yielding_incomplete_group(
    make_api_page: MakePage,
) -> None:
    def pages() -> Iterator[ApiPage]:
        yield make_api_page(page=1, pages=2)
        raise ApiResponseError("falhou na página 2")

    with pytest.raises(ApiResponseError):
        next(group_by_request(pages()))


def test_run_bronze_loads_every_request_with_one_run_id(
    make_api_page: MakePage,
    fake_db: dict[str, MagicMock],
    mocker: MockerFixture,
) -> None:
    def fake_iter_pages(
        path: str, params: dict[str, str] | None = None
    ) -> list[ApiPage]:
        return [make_api_page(path=path, params=params)]

    client = mocker.MagicMock()
    client.iter_pages.side_effect = fake_iter_pages
    settings = mocker.MagicMock(spec=Settings)
    settings.indicators = ["SP.POP.TOTL", "NY.GDP.PCAP.CD"]
    settings.source_id = 2

    results = run_bronze(client, MagicMock(), settings, 2000, 2024)

    endpoints = [r.endpoint for r in results]
    assert endpoints == [
        "region",
        "incomelevel",
        "lendingtypes",
        "country",
        "sources",
        "topic",
        "indicator/SP.POP.TOTL",
        "indicator/NY.GDP.PCAP.CD",
        "country/all/indicator/SP.POP.TOTL;NY.GDP.PCAP.CD",
    ]
    run_ids = {call.args[1] for call in fake_db["insert"].call_args_list}
    assert len(run_ids) == 1
    assert client.iter_pages.call_args_list[-1].args[1] == {
        "date": "2000:2024",
        "source": "2",
    }


def test_run_bronze_stops_on_definitive_error(
    make_api_page: MakePage,
    fake_db: dict[str, MagicMock],
    mocker: MockerFixture,
) -> None:
    def fake_iter_pages(
        path: str, params: dict[str, str] | None = None
    ) -> list[ApiPage]:
        if path == "country":
            raise ApiResponseError("Invalid value", code="120")
        return [make_api_page(path=path)]

    client = mocker.MagicMock()
    client.iter_pages.side_effect = fake_iter_pages
    settings = mocker.MagicMock(spec=Settings)
    settings.indicators = ["SP.POP.TOTL"]
    settings.source_id = 2

    with pytest.raises(ApiResponseError):
        run_bronze(client, MagicMock(), settings, 2000, 2024)
    loaded = [call.args[2][0].path for call in fake_db["insert"].call_args_list]
    assert loaded == ["region", "incomelevel", "lendingtypes"]


def test_group_by_request_yields_as_soon_as_last_page_arrives(
    make_api_page: MakePage,
) -> None:
    def pages() -> Iterator[ApiPage]:
        yield make_api_page(path="region")
        raise ApiResponseError("falhou na requisição seguinte")

    groups = group_by_request(pages())

    assert [page.path for page in next(groups)] == ["region"]
    with pytest.raises(ApiResponseError):
        next(groups)


def test_group_by_request_handles_empty_response(make_api_page: MakePage) -> None:
    empty = make_api_page(records=[], page=1, pages=0)

    assert list(group_by_request([empty])) == [[empty]]
