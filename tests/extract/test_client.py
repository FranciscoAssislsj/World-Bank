from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx

from world_bank.config import load_settings
from world_bank.exceptions import ApiResponseError, TransientApiError
from world_bank.extract.client import WorldBankClient, parse_payload


def _ok(payload: Any) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_iter_pages_follows_pagination_until_last_page(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    route = respx_mock.get(f"{base_url}/country").mock(
        side_effect=[
            _ok(make_payload([{"id": "A"}, {"id": "B"}], page=1, pages=3, total=5)),
            _ok(make_payload([{"id": "C"}, {"id": "D"}], page=2, pages=3, total=5)),
            _ok(make_payload([{"id": "E"}], page=3, pages=3, total=5)),
        ]
    )

    pages = list(client.iter_pages("country"))

    assert [page.page for page in pages] == [1, 2, 3]
    assert [r["id"] for page in pages for r in page.records] == list("ABCDE")
    assert route.call_count == 3
    sent = [call.request.url.params for call in route.calls]
    assert [params["page"] for params in sent] == ["1", "2", "3"]
    assert all(params["format"] == "json" for params in sent)
    assert all(params["per_page"] == "2" for params in sent)


def test_page_keeps_original_payload_and_metadata(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    load_fixture: Callable[[str], Any],
) -> None:
    payload = load_fixture("observations_page.json")
    respx_mock.get(f"{base_url}/country/all/indicator/SP.POP.TOTL").mock(
        return_value=_ok(payload)
    )

    (page,) = client.iter_pages("country/all/indicator/SP.POP.TOTL")

    assert page.payload == payload
    assert page.metadata["lastupdated"] == "2026-01-15"
    assert page.total == 2
    assert page.records[1]["value"] is None


def test_get_all_sends_extra_params_and_concatenates_records(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    route = respx_mock.get(f"{base_url}/region").mock(
        side_effect=[
            _ok(make_payload([{"id": "1"}, {"id": "2"}], page=1, pages=2, total=3)),
            _ok(make_payload([{"id": "3"}], page=2, pages=2, total=3)),
        ]
    )

    records = client.get_all("region", {"date": "2000:2001"})

    assert [r["id"] for r in records] == ["1", "2", "3"]
    assert route.calls[1].request.url.params["date"] == "2000:2001"


def test_empty_result_returns_no_records(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    route = respx_mock.get(f"{base_url}/country").mock(
        return_value=_ok(make_payload(None, pages=0, total=0))
    )

    assert client.get_all("country") == []
    assert route.call_count == 1


def test_error_in_body_with_http_200_raises_without_retry(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    load_fixture: Callable[[str], Any],
) -> None:
    route = respx_mock.get(f"{base_url}/indicator/NAO.EXISTE").mock(
        return_value=_ok(load_fixture("error_invalid_value.json"))
    )

    with pytest.raises(ApiResponseError) as exc_info:
        client.get_all("indicator/NAO.EXISTE")

    assert exc_info.value.code == "120"
    assert not isinstance(exc_info.value, TransientApiError)
    assert route.call_count == 1


@pytest.mark.parametrize("code", ["105", "199"])
def test_transient_error_code_in_body_is_retried(
    code: str,
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    error_body = [{"message": [{"id": code, "key": "x", "value": "temporário"}]}]
    route = respx_mock.get(f"{base_url}/topic").mock(
        side_effect=[_ok(error_body), _ok(make_payload([{"id": "1"}]))]
    )

    assert client.get_all("topic") == [{"id": "1"}]
    assert route.call_count == 2


def test_server_error_is_retried_then_succeeds(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    route = respx_mock.get(f"{base_url}/sources").mock(
        side_effect=[httpx.Response(503), _ok(make_payload([{"id": "2"}]))]
    )

    assert client.get_all("sources") == [{"id": "2"}]
    assert route.call_count == 2


def test_persistent_server_error_gives_up_after_max_retries(
    client: WorldBankClient, respx_mock: respx.MockRouter, base_url: str
) -> None:
    route = respx_mock.get(f"{base_url}/sources").mock(return_value=httpx.Response(503))

    with pytest.raises(TransientApiError) as exc_info:
        client.get_all("sources")

    assert exc_info.value.code == "503"
    assert route.call_count == 3


def test_timeout_is_retried_then_succeeds(
    client: WorldBankClient,
    respx_mock: respx.MockRouter,
    base_url: str,
    make_payload: Callable[..., list[Any]],
) -> None:
    route = respx_mock.get(f"{base_url}/region").mock(
        side_effect=[httpx.ConnectTimeout("lento"), _ok(make_payload([{"id": "1"}]))]
    )

    assert client.get_all("region") == [{"id": "1"}]
    assert route.call_count == 2


def test_persistent_timeout_raises_transient_error(
    client: WorldBankClient, respx_mock: respx.MockRouter, base_url: str
) -> None:
    route = respx_mock.get(f"{base_url}/region").mock(
        side_effect=httpx.ReadTimeout("lento")
    )

    with pytest.raises(TransientApiError, match="3 tentativas"):
        client.get_all("region")

    assert route.call_count == 3


def test_client_error_is_not_retried(
    client: WorldBankClient, respx_mock: respx.MockRouter, base_url: str
) -> None:
    route = respx_mock.get(f"{base_url}/nada").mock(return_value=httpx.Response(404))

    with pytest.raises(ApiResponseError) as exc_info:
        client.get_all("nada")

    assert exc_info.value.code == "404"
    assert route.call_count == 1


def test_non_json_body_raises(
    client: WorldBankClient, respx_mock: respx.MockRouter, base_url: str
) -> None:
    respx_mock.get(f"{base_url}/region").mock(
        return_value=httpx.Response(200, content=b"<wb:error/>")
    )

    with pytest.raises(ApiResponseError, match="não é JSON"):
        client.get_all("region")


@pytest.mark.parametrize(
    "payload",
    [
        {"page": 1},
        [],
        [{"page": 1}],
        [{"page": 1}, "texto"],
        ["texto", []],
    ],
)
def test_parse_payload_rejects_unexpected_structure(payload: Any) -> None:
    with pytest.raises(ApiResponseError):
        parse_payload(payload)


@pytest.mark.parametrize("messages", [[], "texto", ["texto"]])
def test_parse_payload_handles_malformed_error_message(messages: Any) -> None:
    with pytest.raises(ApiResponseError, match="erro sem descrição") as exc_info:
        parse_payload([{"message": messages}])

    assert exc_info.value.code is None


def test_from_settings_uses_configured_base_url_and_per_page(
    respx_mock: respx.MockRouter, make_payload: Callable[..., list[Any]]
) -> None:
    settings = load_settings("dev")
    route = respx_mock.get(f"{settings.api_base_url}/region").mock(
        return_value=_ok(make_payload([]))
    )

    with WorldBankClient.from_settings(settings) as wb_client:
        wb_client.get_all("region")

    assert route.calls[0].request.url.params["per_page"] == str(settings.per_page)
