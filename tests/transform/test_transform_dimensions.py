from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from world_bank.exceptions import SchemaValidationError
from world_bank.transform.dimensions import (
    clean_text,
    ensure_unique,
    transform_countries,
    transform_income_levels,
    transform_indicator_topics,
    transform_indicators,
    transform_lending_types,
    transform_regions,
    transform_sources,
    transform_topics,
)


def _country(**overrides: Any) -> dict[str, Any]:
    """Registro inventado de um país real, no formato do endpoint ``country``."""
    record = {
        "id": "XAA",
        "iso2Code": "XA",
        "name": " Terra Inventada ",
        "region": {"id": "REG"},
        "adminregion": {"id": ""},
        "incomeLevel": {"id": "HIC"},
        "lendingType": {"id": "LNX"},
        "capitalCity": "Capital",
        "longitude": "-10.5",
        "latitude": "20.25",
    }
    return {**record, **overrides}


def _aggregate(**overrides: Any) -> dict[str, Any]:
    """Registro inventado de um agregado: a API usa ``NA`` e vazio nas chaves."""
    return _country(
        **{
            "region": {"id": "NA"},
            "incomeLevel": {"id": "NA"},
            "lendingType": {"id": ""},
            "capitalCity": "",
            "longitude": "",
            "latitude": "",
            **overrides,
        }
    )


def _countries(*records: dict[str, Any]) -> list[dict[str, Any]]:
    return transform_countries(records, ["REG", "GRP"], ["HIC", "LIC"], ["LNX", "IBD"])


def _source(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": "2",
        "code": "WDI",
        "name": " Fonte Inventada ",
        "concepts": "3",
        "lastupdated": "2026-01-31",
        "dataavailability": "Y",
        "metadataavailability": "N",
    }
    return {**record, **overrides}


def _indicator(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": "AA.BB.CC",
        "name": " Indicador ",
        "source": {"id": "2"},
        "sourceNote": "",
        "sourceOrganization": " Org ",
        "topics": [{"id": "1", "value": "Tema "}],
    }
    return {**record, **overrides}


@pytest.mark.parametrize(
    ("value", "expected"),
    [("  texto  ", "texto"), ("", None), ("   ", None), (None, None), (5, "5")],
)
def test_clean_text(value: Any, expected: str | None) -> None:
    assert clean_text(value) == expected


def test_region_key_comes_from_code_not_id() -> None:
    rows = transform_regions(
        [
            {"id": "", "code": "GRP", "iso2code": "G1", "name": " Grupo "},
            {"id": "7", "code": "REG", "iso2code": "R1", "name": "Região"},
        ]
    )

    assert rows == [
        {
            "regiao_id": "GRP",
            "regiao_iso2": "G1",
            "nome": "Grupo",
            "e_geografica": False,
        },
        {
            "regiao_id": "REG",
            "regiao_iso2": "R1",
            "nome": "Região",
            "e_geografica": True,
        },
    ]


@pytest.mark.parametrize(
    ("level_id", "order", "is_group"),
    [
        ("LIC", 1, False),
        ("LMC", 2, False),
        ("UMC", 3, False),
        ("HIC", 4, False),
        ("INX", None, False),
        ("LMY", None, True),
        ("MIC", None, True),
    ],
)
def test_income_level_gets_order_and_group_flag(
    level_id: str, order: int | None, is_group: bool
) -> None:
    rows = transform_income_levels([{"id": level_id, "iso2code": "X1", "value": "N"}])

    assert rows[0]["ordem"] == order
    assert rows[0]["e_agrupamento"] is is_group


def test_unknown_income_level_fails() -> None:
    with pytest.raises(SchemaValidationError, match="desconhecido 'NEW'"):
        transform_income_levels([{"id": "NEW", "iso2code": "X1", "value": "Novo"}])


def test_lending_type_row() -> None:
    rows = transform_lending_types([{"id": "IBD", "iso2code": "XF", "value": "IBRD "}])

    assert rows == [
        {"tipo_emprestimo_id": "IBD", "tipo_emprestimo_iso2": "XF", "nome": "IBRD"}
    ]


def test_real_country_has_keys_and_numeric_coordinates() -> None:
    row = _countries(_country())[0]

    assert row == {
        "pais_iso3": "XAA",
        "pais_iso2": "XA",
        "nome": "Terra Inventada",
        "regiao_id": "REG",
        "nivel_renda_atual_id": "HIC",
        "tipo_emprestimo_atual_id": "LNX",
        "regiao_administrativa_id": None,
        "capital": "Capital",
        "latitude": Decimal("20.25"),
        "longitude": Decimal("-10.5"),
        "e_agregado": False,
        "tipo_agregado": None,
    }


def test_admin_region_is_kept_when_present() -> None:
    row = _countries(_country(adminregion={"id": "GRP"}))[0]

    assert row["regiao_administrativa_id"] == "GRP"


def test_country_without_admin_region_field_is_accepted() -> None:
    record = _country()
    del record["adminregion"]

    assert _countries(record)[0]["regiao_administrativa_id"] is None


def test_aggregate_has_null_keys() -> None:
    row = _countries(_aggregate())[0]

    assert row["e_agregado"] is True
    assert row["regiao_id"] is None
    assert row["nivel_renda_atual_id"] is None
    assert row["tipo_emprestimo_atual_id"] is None
    assert row["latitude"] is None
    assert row["capital"] is None


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("GRP", "regiao"),
        ("LIC", "renda"),
        ("IBD", "tipo_emprestimo"),
        ("ZZZ", "outro"),
    ],
)
def test_aggregate_type_follows_dimension_that_has_the_code(
    code: str, expected: str
) -> None:
    assert _countries(_aggregate(id=code))[0]["tipo_agregado"] == expected


def test_real_country_without_capital_or_latitude_is_not_aggregate() -> None:
    row = _countries(_country(capitalCity="", latitude="", longitude=""))[0]

    assert row["e_agregado"] is False
    assert row["capital"] is None
    assert row["latitude"] is None


def test_country_without_region_field_fails() -> None:
    record = _country()
    del record["region"]

    with pytest.raises(SchemaValidationError, match="'region' ausente"):
        _countries(record)


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity"])
def test_invalid_latitude_fails(value: str) -> None:
    with pytest.raises(SchemaValidationError, match="latitude"):
        _countries(_country(latitude=value))


def test_latitude_out_of_range_fails() -> None:
    with pytest.raises(SchemaValidationError, match="fora da faixa"):
        _countries(_country(latitude="90.5"))


def test_longitude_out_of_range_fails() -> None:
    with pytest.raises(SchemaValidationError, match="fora da faixa"):
        _countries(_country(longitude="-180.5"))


def test_source_converts_types() -> None:
    assert transform_sources([_source()]) == [
        {
            "fonte_id": 2,
            "codigo": "WDI",
            "nome": "Fonte Inventada",
            "conceitos": 3,
            "ultima_atualizacao": date(2026, 1, 31),
            "tem_dados": True,
            "tem_metadados": False,
        }
    ]


def test_source_empty_metadata_flag_is_none_not_false() -> None:
    row = transform_sources([_source(metadataavailability="")])[0]

    assert row["tem_metadados"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"lastupdated": "31/01/2026"}, "data inválida"),
        ({"dataavailability": "S"}, "fora de Y/N"),
        ({"metadataavailability": "talvez"}, "fora de Y/N"),
        ({"dataavailability": ""}, "'dataavailability' ausente"),
        ({"concepts": "três"}, "inteiro inválido"),
        ({"code": " "}, "'code' ausente"),
    ],
)
def test_invalid_source_fails(overrides: dict[str, str], message: str) -> None:
    with pytest.raises(SchemaValidationError, match=message):
        transform_sources([_source(**overrides)])


def test_topic_row() -> None:
    rows = transform_topics([{"id": "3", "value": " Tema ", "sourceNote": ""}])

    assert rows == [{"topico_id": 3, "nome": "Tema", "descricao": None}]


def test_indicator_row() -> None:
    assert transform_indicators([_indicator()]) == [
        {
            "indicador_id": "AA.BB.CC",
            "nome": "Indicador",
            "fonte_id": 2,
            "descricao": None,
            "organizacao_fonte": "Org",
        }
    ]


def test_indicator_with_invalid_source_fails() -> None:
    with pytest.raises(SchemaValidationError, match="inteiro inválido"):
        transform_indicators([_indicator(source={"id": ""})])


def test_links_use_topic_id_and_generate_one_row_per_topic() -> None:
    topics = [{"id": "1", "value": "A "}, {"id": "2"}, {"id": "3"}]

    rows = transform_indicator_topics([_indicator(topics=topics)])

    assert rows == [
        {"indicador_id": "AA.BB.CC", "topico_id": 1},
        {"indicador_id": "AA.BB.CC", "topico_id": 2},
        {"indicador_id": "AA.BB.CC", "topico_id": 3},
    ]


def test_indicator_without_topics_field_fails() -> None:
    with pytest.raises(SchemaValidationError, match="'topics' ausente"):
        transform_indicator_topics([_indicator(topics=None)])


def test_topic_without_id_fails() -> None:
    with pytest.raises(SchemaValidationError, match="'id' ausente"):
        transform_indicator_topics([_indicator(topics=[{}])])


def test_repeated_key_fails() -> None:
    record = {"id": "", "code": "REG", "iso2code": "R1", "name": "Região"}

    with pytest.raises(SchemaValidationError, match="chave repetida"):
        transform_regions([record, {**record, "iso2code": "R2"}])


def test_ensure_unique_accepts_same_value_in_part_of_the_key() -> None:
    rows = [{"a": 1, "b": 1}, {"a": 1, "b": 2}]

    assert ensure_unique(rows, "t", ["a", "b"]) == rows
