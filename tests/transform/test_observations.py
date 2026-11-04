from decimal import Decimal
from typing import Any

import pytest

from world_bank.exceptions import SchemaValidationError
from world_bank.transform.observations import transform_observations

CODES = {"XA": "XAA", "1W": "WLD", "XD": "HIC"}
INDICATORS = {"AA.BB"}


def _record(**overrides: Any) -> dict[str, Any]:
    """Registro inventado, no formato de ``country/all/indicator/{ids}``."""
    record = {
        "indicator": {"id": "AA.BB", "value": "Indicador"},
        "country": {"id": "XA", "value": "Terra"},
        "countryiso3code": "XAA",
        "date": "2023",
        "value": 12.5,
        "unit": "",
        "obs_status": "",
        "decimal": 1,
    }
    return {**record, **overrides}


def _transform(*records: dict[str, Any]) -> list[dict[str, Any]]:
    return transform_observations(records, CODES, INDICATORS)


def test_builds_clean_row() -> None:
    assert _transform(_record()) == [
        {
            "pais_iso3": "XAA",
            "indicador_id": "AA.BB",
            "ano": 2023,
            "valor": Decimal("12.5"),
            "casas_decimais": 1,
        }
    ]


def test_null_value_is_kept() -> None:
    assert _transform(_record(value=None))[0]["valor"] is None


def test_zero_stays_zero() -> None:
    assert _transform(_record(value=0))[0]["valor"] == Decimal(0)


def test_aggregate_without_iso3_is_found_by_country_id() -> None:
    record = _record(country={"id": "XD", "value": "High income"}, countryiso3code="")

    assert _transform(record)[0]["pais_iso3"] == "HIC"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (8062923417, "8062923417"),
        (111669432109121, "111669432109121"),
        (60.6068586411829, "60.6068586411829"),
        (-16.8596910540644, "-16.8596910540644"),
    ],
)
def test_value_keeps_every_digit(value: float, expected: str) -> None:
    assert _transform(_record(value=value))[0]["valor"] == Decimal(expected)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"date": "2020Q1"}, "ano inválido"),
        ({"date": "20"}, "ano inválido"),
        ({"date": ""}, "ano inválido"),
        ({"value": "12.5"}, "não numérico"),
        ({"value": True}, "não numérico"),
        ({"decimal": "1"}, "'decimal' inválido"),
        ({"decimal": True}, "'decimal' inválido"),
        ({"decimal": -1}, "'decimal' inválido"),
        ({"decimal": None}, "'decimal' inválido"),
        ({"country": None}, r"country\.id ausente"),
        ({"country": {"id": ""}}, r"country\.id ausente"),
        ({"indicator": {}}, r"indicator\.id ausente"),
        ({"country": {"id": "ZZ"}}, "rode load-dimensions"),
        ({"indicator": {"id": "CC.DD"}}, "fora da configuração"),
    ],
)
def test_invalid_record_fails(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(SchemaValidationError, match=message):
        _transform(_record(**overrides))


def test_missing_value_field_fails() -> None:
    record = _record()
    del record["value"]

    with pytest.raises(SchemaValidationError, match="'value' ausente"):
        _transform(record)
