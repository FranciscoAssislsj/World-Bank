from collections.abc import Callable
from typing import Any

import pytest

from world_bank.exceptions import SchemaValidationError
from world_bank.transform.income_history import transform_income_history

MakeWorkbook = Callable[..., bytes]


def test_generates_one_row_per_country_and_year(
    make_income_workbook: MakeWorkbook,
) -> None:
    content = make_income_workbook(
        [["XAA", "Terra", "L", "LM"], ["XBB", "B", "UM", "H"]]
    )

    rows = transform_income_history(content, ["XAA", "XBB"])

    assert rows == [
        _row("XAA", 2024, 2026, "LIC"),
        _row("XAA", 2025, 2027, "LMC"),
        _row("XBB", 2024, 2026, "UMC"),
        _row("XBB", 2025, 2027, "HIC"),
    ]


def _row(country: str, data_year: int, fiscal_year: int, level: str) -> dict[str, Any]:
    return {
        "pais_iso3": country,
        "ano_referencia": data_year,
        "ano_fiscal": fiscal_year,
        "nivel_renda_id": level,
    }


@pytest.mark.parametrize("value", ["..", None, " "])
def test_unclassified_year_generates_no_row(
    make_income_workbook: MakeWorkbook, value: str | None
) -> None:
    content = make_income_workbook([["XAA", "Terra", value, "H"]])

    rows = transform_income_history(content, ["XAA"])

    assert [row["ano_referencia"] for row in rows] == [2025]


def test_asterisk_is_only_a_footnote(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "Terra", "LM*", "LM"]])

    rows = transform_income_history(content, ["XAA"])

    assert rows[0]["nivel_renda_id"] == "LMC"


def test_fiscal_years_before_2000_keep_the_century(
    make_income_workbook: MakeWorkbook,
) -> None:
    content = make_income_workbook(
        [["XAA", "Terra", "L", "L"]], fiscal=("FY99", "FY00"), years=(1997, 1998)
    )

    rows = transform_income_history(content, ["XAA"])

    assert [row["ano_fiscal"] for row in rows] == [1999, 2000]


def test_economies_without_catalog_are_skipped(
    make_income_workbook: MakeWorkbook,
) -> None:
    content = make_income_workbook(
        [["XAA", "Terra", "L", "L"], ["YUGf", "Iugoslávia", "UM", ".."]]
    )

    rows = transform_income_history(content, ["XAA"])

    assert {row["pais_iso3"] for row in rows} == {"XAA"}


def test_notes_without_code_are_ignored(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook(
        [["XAA", "Terra", "L", "L"], [None, "Nota de rodapé", None, None]]
    )

    assert len(transform_income_history(content, ["XAA"])) == 2


def test_unknown_code_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XZZ", "Nova", "L", "L"], ["XAA", "T", "L", "L"]])

    with pytest.raises(SchemaValidationError, match="'XZZ' não está em pais"):
        transform_income_history(content, ["XAA"])


def test_missing_country_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "Terra", "L", "L"]])

    with pytest.raises(SchemaValidationError, match=r"fora do arquivo: \['XBB'\]"):
        transform_income_history(content, ["XAA", "XBB"])


def test_unknown_level_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "Terra", "M", "L"]])

    with pytest.raises(SchemaValidationError, match="desconhecida 'M' em XAA, 2024"):
        transform_income_history(content, ["XAA"])


def test_year_that_does_not_match_fiscal_year_fails(
    make_income_workbook: MakeWorkbook,
) -> None:
    content = make_income_workbook([["XAA", "T", "L", "L"]], years=(2024, 2030))

    with pytest.raises(SchemaValidationError, match="deveria usar dados de 2025"):
        transform_income_history(content, ["XAA"])


def test_invalid_fiscal_year_label_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "T", "L", "L"]], fiscal=("FY26", "2027"))

    with pytest.raises(SchemaValidationError, match="ano fiscal inválido"):
        transform_income_history(content, ["XAA"])


def test_missing_sheet_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "T", "L", "L"]], sheet="Outra aba")

    with pytest.raises(SchemaValidationError, match="não encontrada"):
        transform_income_history(content, ["XAA"])


def test_missing_header_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "T", "L", "L"]], with_header=False)

    with pytest.raises(SchemaValidationError, match="cabeçalho de anos"):
        transform_income_history(content, ["XAA"])


def test_header_without_year_columns_fails(make_income_workbook: MakeWorkbook) -> None:
    content = make_income_workbook([["XAA", "T"]], fiscal=(), years=())

    with pytest.raises(SchemaValidationError, match="nenhuma coluna de ano"):
        transform_income_history(content, ["XAA"])


def test_file_that_is_not_excel_fails() -> None:
    with pytest.raises(SchemaValidationError, match="arquivo ilegível"):
        transform_income_history(b"PK nao e um excel", ["XAA"])
