import pytest
from pytest_mock import MockerFixture

from world_bank.extract.endpoints import (
    MAX_INDICATORS_PER_REQUEST,
    chunk_indicators,
    fetch_dimension,
    fetch_indicator_metadata,
    fetch_observations,
)


@pytest.mark.parametrize(
    ("dimension", "path"),
    [
        ("region", "region"),
        ("income_level", "incomelevel"),
        ("lending_type", "lendingtypes"),
        ("country", "country"),
        ("source", "sources"),
        ("topic", "topic"),
    ],
)
def test_fetch_dimension_maps_to_api_path(
    mocker: MockerFixture, dimension: str, path: str
) -> None:
    client = mocker.Mock()

    fetch_dimension(client, dimension)  # type: ignore[arg-type]

    client.iter_pages.assert_called_once_with(path)


def test_fetch_dimension_rejects_unknown_name(mocker: MockerFixture) -> None:
    with pytest.raises(ValueError, match="desconhecida"):
        fetch_dimension(mocker.Mock(), "planeta")  # type: ignore[arg-type]


def test_fetch_indicator_metadata_requests_each_indicator(
    mocker: MockerFixture,
) -> None:
    client = mocker.Mock()
    client.iter_pages.side_effect = lambda path: iter([path])

    pages = list(fetch_indicator_metadata(client, ["SP.POP.TOTL", "NY.GDP.PCAP.CD"]))

    assert pages == ["indicator/SP.POP.TOTL", "indicator/NY.GDP.PCAP.CD"]


def test_fetch_observations_builds_path_and_params(mocker: MockerFixture) -> None:
    client = mocker.Mock()
    client.iter_pages.return_value = iter(["page"])

    pages = list(
        fetch_observations(client, ["SP.POP.TOTL", "SI.POV.GINI"], 2000, 2024, 2)
    )

    assert pages == ["page"]
    client.iter_pages.assert_called_once_with(
        "country/all/indicator/SP.POP.TOTL;SI.POV.GINI",
        {"date": "2000:2024", "source": "2"},
    )


def test_fetch_observations_rejects_inverted_period(mocker: MockerFixture) -> None:
    with pytest.raises(ValueError, match="start_year"):
        list(fetch_observations(mocker.Mock(), ["SP.POP.TOTL"], 2024, 2000, 2))


def test_chunk_indicators_respects_max_items() -> None:
    ids = [f"IND.{n}" for n in range(MAX_INDICATORS_PER_REQUEST + 1)]

    chunks = chunk_indicators(ids)

    assert [len(chunk) for chunk in chunks] == [MAX_INDICATORS_PER_REQUEST, 1]
    assert [i for chunk in chunks for i in chunk] == ids


def test_chunk_indicators_respects_max_chars() -> None:
    # "AAAA;BBBB" tem 9 caracteres; um terceiro código passaria de 10.
    chunks = chunk_indicators(["AAAA", "BBBB", "CCCC"], max_chars=10)

    assert chunks == [["AAAA", "BBBB"], ["CCCC"]]


def test_chunk_indicators_empty_list() -> None:
    assert chunk_indicators([]) == []


@pytest.mark.parametrize("bad_id", ["SP/POP", "A;B", "", "SP POP"])
def test_invalid_indicator_id_is_rejected(bad_id: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        chunk_indicators([bad_id])
