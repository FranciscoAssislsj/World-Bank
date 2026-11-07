"""Transforma os cadastros da API em linhas das dimensões da silver.

As funções são puras (D-031): recebem os registros como vieram da API e devolvem
as linhas limpas, sem acessar rede nem banco. Um dado fora do esperado gera
``SchemaValidationError`` em vez de ser gravado errado (D-006).
"""

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from world_bank.exceptions import SchemaValidationError

type Record = dict[str, Any]
type Row = dict[str, Any]

# Código que a API usa em agregados no lugar de região e nível de renda (D-017).
_NOT_APPLICABLE = "NA"

# (ordem, e_agrupamento) de cada nível de renda (D-034).
_INCOME_LEVELS: dict[str, tuple[int | None, bool]] = {
    "LIC": (1, False),
    "LMC": (2, False),
    "UMC": (3, False),
    "HIC": (4, False),
    "INX": (None, False),
    "LMY": (None, True),
    "MIC": (None, True),
}

_YES_NO = {"Y": True, "N": False}


def clean_text(value: Any) -> str | None:
    """Remove espaços das pontas e converte texto vazio em ``None`` (D-018).

    Args:
        value: Valor vindo da API.

    Returns:
        O texto limpo, ou ``None`` se não houver conteúdo.
    """
    if value is None:
        return None
    return str(value).strip() or None


def transform_regions(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.regiao``.

    Args:
        records: Registros do endpoint ``region``.

    Returns:
        Uma linha por região.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório ou a chave repetir.
    """
    table = "regiao"
    rows = [
        {
            "regiao_id": _required(record, table, "code"),
            "regiao_iso2": _required(record, table, "iso2code"),
            "nome": _required(record, table, "name"),
            "e_geografica": clean_text(record.get("id")) is not None,
        }
        for record in records
    ]
    return ensure_unique(rows, table, ["regiao_id"])


def transform_income_levels(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.nivel_renda``.

    Args:
        records: Registros do endpoint ``incomelevel``.

    Returns:
        Uma linha por nível de renda.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório, o código não for
            conhecido ou a chave repetir.
    """
    table = "nivel_renda"
    rows = []
    for record in records:
        level_id = _required(record, table, "id")
        if level_id not in _INCOME_LEVELS:
            raise SchemaValidationError(
                f"{table}: nível de renda desconhecido {level_id!r}; "
                "revise a lista de níveis (D-034)"
            )
        order, is_group = _INCOME_LEVELS[level_id]
        rows.append(
            {
                "nivel_renda_id": level_id,
                "nivel_renda_iso2": _required(record, table, "iso2code"),
                "nome": _required(record, table, "value"),
                "ordem": order,
                "e_agrupamento": is_group,
            }
        )
    return ensure_unique(rows, table, ["nivel_renda_id"])


def transform_lending_types(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.tipo_emprestimo``.

    Args:
        records: Registros do endpoint ``lendingtypes``.

    Returns:
        Uma linha por tipo de empréstimo.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório ou a chave repetir.
    """
    table = "tipo_emprestimo"
    rows = [
        {
            "tipo_emprestimo_id": _required(record, table, "id"),
            "tipo_emprestimo_iso2": _required(record, table, "iso2code"),
            "nome": _required(record, table, "value"),
        }
        for record in records
    ]
    return ensure_unique(rows, table, ["tipo_emprestimo_id"])


def transform_sources(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.fonte``.

    Args:
        records: Registros do endpoint ``sources``.

    Returns:
        Uma linha por fonte.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório, um valor não puder
            ser convertido ou a chave repetir.
    """
    table = "fonte"
    rows = [
        {
            "fonte_id": _integer(record, table, "id"),
            "codigo": _required(record, table, "code"),
            "nome": _required(record, table, "name"),
            "conceitos": _integer(record, table, "concepts"),
            "ultima_atualizacao": _date(record, table, "lastupdated"),
            "tem_dados": _required_yes_no(record, table, "dataavailability"),
            "tem_metadados": _yes_no(record, table, "metadataavailability"),
        }
        for record in records
    ]
    return ensure_unique(rows, table, ["fonte_id"])


def transform_topics(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.topico``.

    Args:
        records: Registros do endpoint ``topic``.

    Returns:
        Uma linha por tópico.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório, o ``id`` não for
            inteiro ou a chave repetir.
    """
    table = "topico"
    rows = [
        {
            "topico_id": _integer(record, table, "id"),
            "nome": _required(record, table, "value"),
            "descricao": clean_text(record.get("sourceNote")),
        }
        for record in records
    ]
    return ensure_unique(rows, table, ["topico_id"])


def transform_countries(
    records: Iterable[Record],
    region_ids: Iterable[str],
    income_level_ids: Iterable[str],
    lending_type_ids: Iterable[str],
) -> list[Row]:
    """Monta as linhas de ``silver.pais``.

    Os códigos das dimensões servem para classificar os agregados: o agregado de
    uma região tem o mesmo código da região (D-034).

    Args:
        records: Registros do endpoint ``country``.
        region_ids: Valores de ``regiao_id``.
        income_level_ids: Valores de ``nivel_renda_id``.
        lending_type_ids: Valores de ``tipo_emprestimo_id``.

    Returns:
        Uma linha por país ou agregado.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório, a coordenada for
            inválida ou a chave repetir.
    """
    table = "pais"
    regions, income_levels = set(region_ids), set(income_level_ids)
    lending_types = set(lending_type_ids)
    rows = []
    for record in records:
        country_id = _required(record, table, "id")
        is_aggregate = _nested_id(record, table, "region") == _NOT_APPLICABLE
        rows.append(
            {
                "pais_iso3": country_id,
                "pais_iso2": _required(record, table, "iso2Code"),
                "nome": _required(record, table, "name"),
                "regiao_id": _reference(record, table, "region"),
                "nivel_renda_atual_id": _reference(record, table, "incomeLevel"),
                "tipo_emprestimo_atual_id": _reference(record, table, "lendingType"),
                "regiao_administrativa_id": _optional_reference(record, "adminregion"),
                "capital": clean_text(record.get("capitalCity")),
                "latitude": _coordinate(record, table, "latitude", 90),
                "longitude": _coordinate(record, table, "longitude", 180),
                "e_agregado": is_aggregate,
                "tipo_agregado": _aggregate_type(
                    country_id, regions, income_levels, lending_types
                )
                if is_aggregate
                else None,
            }
        )
    return ensure_unique(rows, table, ["pais_iso3"])


def transform_indicators(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.indicador``.

    Args:
        records: Registros de ``indicator/{id}``.

    Returns:
        Uma linha por indicador.

    Raises:
        SchemaValidationError: Se faltar campo obrigatório, a fonte não for
            inteira ou a chave repetir.
    """
    table = "indicador"
    rows = [
        {
            "indicador_id": _required(record, table, "id"),
            "nome": _required(record, table, "name"),
            "fonte_id": _to_int(_nested_id(record, table, "source"), table, record),
            "descricao": clean_text(record.get("sourceNote")),
            "organizacao_fonte": clean_text(record.get("sourceOrganization")),
        }
        for record in records
    ]
    return ensure_unique(rows, table, ["indicador_id"])


def transform_indicator_topics(records: Iterable[Record]) -> list[Row]:
    """Monta as linhas de ``silver.indicador_topico``.

    A ligação usa o ``id`` do tópico, porque o nome vem com espaço sobrando.

    Args:
        records: Registros de ``indicator/{id}``.

    Returns:
        Uma linha por ligação entre indicador e tópico.

    Raises:
        SchemaValidationError: Se faltar ``topics``, um ``id`` for inválido ou a
            ligação repetir.
    """
    table = "indicador_topico"
    rows = []
    for record in records:
        indicator_id = _required(record, table, "id")
        topics = record.get("topics")
        if not isinstance(topics, list):
            raise SchemaValidationError(
                f"{table}: campo 'topics' ausente no registro {record!r}"
            )
        rows.extend(
            {
                "indicador_id": indicator_id,
                "topico_id": _integer(topic, table, "id"),
            }
            for topic in topics
        )
    return ensure_unique(rows, table, ["indicador_id", "topico_id"])


def ensure_unique(rows: list[Row], table: str, key_columns: Sequence[str]) -> list[Row]:
    """Confere que nenhuma chave aparece duas vezes.

    Args:
        rows: Linhas já transformadas.
        table: Nome da tabela, para a mensagem de erro.
        key_columns: Colunas que formam a chave.

    Returns:
        As mesmas linhas.

    Raises:
        SchemaValidationError: Se alguma chave repetir.
    """
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        key = tuple(row[column] for column in key_columns)
        if key in seen:
            raise SchemaValidationError(f"{table}: chave repetida {key!r}")
        seen.add(key)
    return rows


def _required(record: Record, table: str, field: str) -> str:
    value = clean_text(record.get(field))
    if value is None:
        raise SchemaValidationError(
            f"{table}: campo obrigatório {field!r} ausente no registro {record!r}"
        )
    return value


def _nested_id(record: Record, table: str, field: str) -> str | None:
    nested = record.get(field)
    if not isinstance(nested, dict):
        raise SchemaValidationError(
            f"{table}: campo obrigatório {field!r} ausente no registro {record!r}"
        )
    return clean_text(nested.get("id"))


def _reference(record: Record, table: str, field: str) -> str | None:
    """Lê uma chave para outra dimensão; ``NA`` e vazio viram ``None`` (D-017)."""
    value = _nested_id(record, table, field)
    return None if value == _NOT_APPLICABLE else value


def _optional_reference(record: Record, field: str) -> str | None:
    nested = record.get(field)
    return clean_text(nested.get("id")) if isinstance(nested, dict) else None


def _aggregate_type(
    country_id: str,
    regions: set[str],
    income_levels: set[str],
    lending_types: set[str],
) -> str:
    if country_id in regions:
        return "regiao"
    if country_id in income_levels:
        return "renda"
    if country_id in lending_types:
        return "tipo_emprestimo"
    return "outro"


def _to_int(value: str | None, table: str, record: Record) -> int:
    try:
        return int(value or "")
    except ValueError as exc:
        raise SchemaValidationError(
            f"{table}: inteiro inválido {value!r} no registro {record!r}"
        ) from exc


def _integer(record: Record, table: str, field: str) -> int:
    return _to_int(_required(record, table, field), table, record)


def _date(record: Record, table: str, field: str) -> date:
    value = _required(record, table, field)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SchemaValidationError(
            f"{table}: data inválida em {field!r} no registro {record!r}"
        ) from exc


def _yes_no(record: Record, table: str, field: str) -> bool | None:
    value = clean_text(record.get(field))
    if value is None:
        return None
    if value not in _YES_NO:
        raise SchemaValidationError(
            f"{table}: valor fora de Y/N em {field!r} no registro {record!r}"
        )
    return _YES_NO[value]


def _required_yes_no(record: Record, table: str, field: str) -> bool:
    value = _yes_no(record, table, field)
    if value is None:
        raise SchemaValidationError(
            f"{table}: campo obrigatório {field!r} ausente no registro {record!r}"
        )
    return value


def _coordinate(record: Record, table: str, field: str, limit: int) -> Decimal | None:
    value = clean_text(record.get(field))
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise SchemaValidationError(
            f"{table}: número inválido em {field!r} no registro {record!r}"
        ) from exc
    if not number.is_finite() or abs(number) > limit:
        raise SchemaValidationError(
            f"{table}: {field!r} fora da faixa no registro {record!r}"
        )
    return number
