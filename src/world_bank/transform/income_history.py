"""Transforma o histórico oficial de renda (OGHIST) em linhas por país e ano.

Função pura (D-031): recebe os bytes do Excel e devolve as linhas limpas. Se o
formato do arquivo mudar, a função falha em vez de gravar errado (D-006).
"""

from collections.abc import Iterable
from io import BytesIO
from typing import Any
from zipfile import BadZipFile

from openpyxl import load_workbook

from world_bank.exceptions import SchemaValidationError
from world_bank.transform.dimensions import Row, clean_text, ensure_unique

_TABLE = "classificacao_renda_anual"
_SHEET = "Country Analytical History"
_FISCAL_YEAR_LABEL = "Bank's fiscal year:"
_DATA_YEAR_LABEL = "Data for calendar year :"
_FIRST_YEAR_COLUMN = 2

_INCOME_LEVELS = {"L": "LIC", "LM": "LMC", "UM": "UMC", "H": "HIC"}
_NOT_CLASSIFIED = ".."

# Códigos do arquivo sem cadastro na API, logo sem observações para ligar (D-039):
# economias que deixaram de existir (ANT, CSK, SUN, YUG, YUGf), Mayotte e Taiwan.
_NOT_IN_CATALOG = {"ANT", "CSK", "MYT", "SUN", "TWN", "YUG", "YUGf"}


def transform_income_history(content: bytes, country_ids: Iterable[str]) -> list[Row]:
    """Monta as linhas de ``silver.classificacao_renda_anual``.

    Só gera linha quando o país foi classificado naquele ano (D-039).

    Args:
        content: Bytes do arquivo ``.xlsx``.
        country_ids: Códigos ISO3 dos países reais, sem os agregados.

    Returns:
        Uma linha por país e ano.

    Raises:
        SchemaValidationError: Se o formato do arquivo não for o esperado, houver
            valor ou código desconhecido, ou faltar um país.
    """
    sheet_rows = _read_sheet(content)
    header = _find_header(sheet_rows)
    years = _read_years(sheet_rows[header], sheet_rows[header + 1])
    expected = set(country_ids)
    found: set[str] = set()
    rows: list[Row] = []
    for sheet_row in sheet_rows[header + 2 :]:
        country = clean_text(_cell(sheet_row, 0))
        if country is None or country in _NOT_IN_CATALOG:
            continue
        if country not in expected:
            raise SchemaValidationError(
                f"{_TABLE}: código {country!r} não está em pais; revise a D-039"
            )
        found.add(country)
        for column, fiscal_year, data_year in years:
            level = _income_level(_cell(sheet_row, column), country, data_year)
            if level is not None:
                rows.append(
                    {
                        "pais_iso3": country,
                        "ano_referencia": data_year,
                        "ano_fiscal": fiscal_year,
                        "nivel_renda_id": level,
                    }
                )
    if missing := sorted(expected - found):
        raise SchemaValidationError(f"{_TABLE}: países fora do arquivo: {missing}")
    return ensure_unique(rows, _TABLE, ["pais_iso3", "ano_referencia"])


def _read_sheet(content: bytes) -> list[tuple[Any, ...]]:
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, KeyError, ValueError, OSError) as exc:
        raise SchemaValidationError(f"{_TABLE}: arquivo ilegível: {exc}") from exc
    try:
        if _SHEET not in workbook.sheetnames:
            raise SchemaValidationError(f"{_TABLE}: aba {_SHEET!r} não encontrada")
        return list(workbook[_SHEET].iter_rows(values_only=True))
    finally:
        workbook.close()


def _find_header(sheet_rows: list[tuple[Any, ...]]) -> int:
    for index, row in enumerate(sheet_rows[:-1]):
        if (
            clean_text(_cell(row, 1)) == _FISCAL_YEAR_LABEL
            and clean_text(_cell(sheet_rows[index + 1], 1)) == _DATA_YEAR_LABEL
        ):
            return index
    raise SchemaValidationError(f"{_TABLE}: cabeçalho de anos não encontrado")


def _read_years(
    fiscal_row: tuple[Any, ...], data_row: tuple[Any, ...]
) -> list[tuple[int, int, int]]:
    """Devolve ``(coluna, ano fiscal, ano de referência)`` de cada coluna de ano."""
    years = []
    for column in range(_FIRST_YEAR_COLUMN, len(fiscal_row)):
        label = clean_text(fiscal_row[column])
        if label is None:
            continue
        fiscal_year = _fiscal_year(label)
        data_year = _cell(data_row, column)
        if data_year != fiscal_year - 2:
            raise SchemaValidationError(
                f"{_TABLE}: {label} deveria usar dados de {fiscal_year - 2}, "
                f"mas o arquivo indica {data_year!r}"
            )
        years.append((column, fiscal_year, data_year))
    if not years:
        raise SchemaValidationError(f"{_TABLE}: nenhuma coluna de ano encontrada")
    return years


def _fiscal_year(label: str) -> int:
    """Converte ``FY27`` em 2027 e ``FY89`` em 1989."""
    digits = label.removeprefix("FY")
    if not (label.startswith("FY") and len(digits) == 2 and digits.isdigit()):
        raise SchemaValidationError(f"{_TABLE}: ano fiscal inválido {label!r}")
    year = int(digits)
    return 1900 + year if year >= 50 else 2000 + year


def _income_level(value: Any, country: str, year: int) -> str | None:
    text = clean_text(value)
    if text is None or text == _NOT_CLASSIFIED:
        return None
    # O asterisco é só uma nota de rodapé do arquivo (Iêmen em FY89 e FY90).
    level = _INCOME_LEVELS.get(text.rstrip("*"))
    if level is None:
        raise SchemaValidationError(
            f"{_TABLE}: classificação desconhecida {text!r} em {country}, {year}"
        )
    return level


def _cell(row: tuple[Any, ...], column: int) -> Any:
    return row[column] if column < len(row) else None
