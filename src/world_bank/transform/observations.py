"""Transforma as observações da API em linhas de ``silver.fato_observacao``.

Função pura (D-031): recebe os registros como vieram da API e devolve as linhas
limpas. Um dado fora do esperado gera ``SchemaValidationError`` (D-006).
"""

from collections.abc import Collection, Iterable, Mapping
from decimal import Decimal
from typing import Any

from world_bank.exceptions import SchemaValidationError
from world_bank.transform.dimensions import Record, Row, clean_text

_TABLE = "fato_observacao"
KEY_COLUMNS = ("pais_iso3", "indicador_id", "ano")


def transform_observations(
    records: Iterable[Record],
    country_codes: Mapping[str, str],
    indicator_ids: Collection[str],
) -> list[Row]:
    """Monta as linhas de ``silver.fato_observacao``.

    O país é encontrado pelo ``country.id``, e não pelo ``countryiso3code``, que
    vem vazio em alguns agregados (D-041). Valor nulo é mantido (D-042).

    Args:
        records: Registros de ``country/all/indicator/{ids}``.
        country_codes: Mapa de ``pais_iso2`` para ``pais_iso3``.
        indicator_ids: Indicadores aceitos (os da configuração).

    Returns:
        Uma linha por registro.

    Raises:
        SchemaValidationError: Se um campo faltar ou for inválido, ou se o país
            ou o indicador forem desconhecidos.
    """
    return [
        {
            "pais_iso3": _country(record, country_codes),
            "indicador_id": _indicator(record, indicator_ids),
            "ano": _year(record),
            "valor": _value(record),
            "casas_decimais": _decimal_places(record),
        }
        for record in records
    ]


def _nested_id(record: Record, field: str) -> str:
    nested = record.get(field)
    value = clean_text(nested.get("id")) if isinstance(nested, dict) else None
    if value is None:
        raise SchemaValidationError(
            f"{_TABLE}: campo obrigatório {field}.id ausente no registro {record!r}"
        )
    return value


def _country(record: Record, country_codes: Mapping[str, str]) -> str:
    code = _nested_id(record, "country")
    if code not in country_codes:
        raise SchemaValidationError(
            f"{_TABLE}: país {code!r} não está em dim_pais; rode load-dimensions"
        )
    return country_codes[code]


def _indicator(record: Record, indicator_ids: Collection[str]) -> str:
    indicator = _nested_id(record, "indicator")
    if indicator not in indicator_ids:
        raise SchemaValidationError(
            f"{_TABLE}: indicador {indicator!r} fora da configuração"
        )
    return indicator


def _year(record: Record) -> int:
    value = clean_text(record.get("date"))
    if value is None or len(value) != 4 or not value.isascii() or not value.isdigit():
        raise SchemaValidationError(
            f"{_TABLE}: ano inválido em 'date' no registro {record!r} (D-040)"
        )
    return int(value)


def _value(record: Record) -> Decimal | None:
    if "value" not in record:
        raise SchemaValidationError(
            f"{_TABLE}: campo obrigatório 'value' ausente no registro {record!r}"
        )
    value: Any = record["value"]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SchemaValidationError(
            f"{_TABLE}: valor não numérico em 'value' no registro {record!r}"
        )
    return Decimal(str(value))


def _decimal_places(record: Record) -> int:
    value = record.get("decimal")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchemaValidationError(
            f"{_TABLE}: 'decimal' inválido no registro {record!r}"
        )
    return value
