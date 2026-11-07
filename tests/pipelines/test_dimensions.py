from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, call
from uuid import uuid4

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.exceptions import LoadError, SchemaValidationError
from world_bank.load.postgres import BronzeLoad, SourceFile
from world_bank.pipelines.dimensions import (
    TableRows,
    build_tables,
    run_dimensions,
    write_tables,
)

WRITE_ORDER = [
    "regiao",
    "nivel_renda",
    "tipo_emprestimo",
    "fonte",
    "topico",
    "pais",
    "classificacao_renda_anual",
    "indicador",
    "indicador_topico",
]

RECORDS: dict[str, list[dict[str, Any]]] = {
    "region": [{"id": "1", "code": "REG", "iso2code": "R1", "name": "Região"}],
    "incomelevel": [{"id": "HIC", "iso2code": "H1", "value": "High income"}],
    "lendingtypes": [{"id": "LNX", "iso2code": "L1", "value": "Not classified"}],
    "country": [
        {
            "id": "XAA",
            "iso2Code": "XA",
            "name": "Terra",
            "region": {"id": "REG"},
            "adminregion": {"id": ""},
            "incomeLevel": {"id": "HIC"},
            "lendingType": {"id": "LNX"},
            "capitalCity": "Capital",
            "longitude": "1.5",
            "latitude": "2.5",
        }
    ],
    "sources": [
        {
            "id": "2",
            "code": "WDI",
            "name": "Fonte",
            "concepts": "3",
            "lastupdated": "2026-01-31",
            "dataavailability": "Y",
            "metadataavailability": "",
        }
    ],
    "topic": [{"id": "1", "value": "Tema", "sourceNote": ""}],
    "indicator/AA": [
        {
            "id": "AA",
            "name": "Indicador",
            "source": {"id": "2"},
            "sourceNote": "",
            "sourceOrganization": "",
            "topics": [{"id": "1"}],
        }
    ],
}


def _load(endpoint: str) -> BronzeLoad:
    return BronzeLoad(endpoint, uuid4(), RECORDS[endpoint])


def _catalogs() -> dict[str, BronzeLoad]:
    return {
        "region": _load("region"),
        "income_level": _load("incomelevel"),
        "lending_type": _load("lendingtypes"),
        "country": _load("country"),
        "source": _load("sources"),
        "topic": _load("topic"),
    }


@pytest.fixture
def income_file(make_income_workbook: Callable[..., bytes]) -> SourceFile:
    """Histórico inventado com o único país de ``RECORDS``, em um só ano."""
    content = make_income_workbook(
        [["XAA", "Terra", "H"]], fiscal=("FY26",), years=(2024,)
    )
    return SourceFile("income_history", uuid4(), content, "hash")


def _table(name: str, rows: list[dict[str, Any]]) -> TableRows:
    return TableRows(name, ("id",), rows)


def test_build_tables_follows_foreign_key_order(income_file: SourceFile) -> None:
    tables = build_tables(_catalogs(), [_load("indicator/AA")], income_file)

    assert [table.table for table in tables] == WRITE_ORDER
    assert all(len(table.rows) == 1 for table in tables)


def test_each_row_gets_the_run_id_of_its_own_load(income_file: SourceFile) -> None:
    catalogs = _catalogs()
    indicator = _load("indicator/AA")

    tables = {t.table: t for t in build_tables(catalogs, [indicator], income_file)}

    assert tables["pais"].rows[0]["bronze_run_id"] == catalogs["country"].run_id
    assert tables["regiao"].rows[0]["bronze_run_id"] == catalogs["region"].run_id
    assert tables["indicador"].rows[0]["bronze_run_id"] == indicator.run_id
    income = tables["classificacao_renda_anual"].rows[0]
    assert income["bronze_run_id"] == income_file.run_id
    link = tables["indicador_topico"].rows[0]
    assert link["bronze_run_id"] == indicator.run_id


def test_same_indicator_in_two_loads_fails(income_file: SourceFile) -> None:
    with pytest.raises(SchemaValidationError, match="chave repetida"):
        build_tables(
            _catalogs(), [_load("indicator/AA"), _load("indicator/AA")], income_file
        )


def test_write_tables_uses_one_transaction_and_syncs_links(
    mocker: MockerFixture,
) -> None:
    upsert = mocker.patch("world_bank.pipelines.dimensions.upsert_rows", return_value=1)
    delete = mocker.patch(
        "world_bank.pipelines.dimensions.delete_missing_links", return_value=2
    )
    conn = MagicMock()
    links = [{"indicador_id": "AA", "topico_id": 1}]
    tables = [
        _table("regiao", [{"id": "REG"}]),
        _table("indicador_topico", links),
    ]

    results = write_tables(conn, tables, ["AA"])

    conn.transaction.assert_called_once_with()
    assert upsert.call_args_list == [
        call(conn, "regiao", ("id",), [{"id": "REG"}]),
        call(conn, "indicador_topico", ("id",), links),
    ]
    delete.assert_called_once_with(conn, ["AA"], [("AA", 1)])
    assert [(r.table, r.rows_read, r.rows_written) for r in results] == [
        ("regiao", 1, 1),
        ("indicador_topico", 1, 3),
    ]


def test_database_error_becomes_load_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "world_bank.pipelines.dimensions.upsert_rows",
        side_effect=psycopg.errors.ForeignKeyViolation("chave inexistente"),
    )
    tables = [_table("regiao", [{"id": "REG"}])]

    with pytest.raises(LoadError, match="chave inexistente"):
        write_tables(MagicMock(), tables, [])


def test_run_dimensions_reads_bronze_and_writes_all_tables(
    mocker: MockerFixture, income_file: SourceFile
) -> None:
    mocker.patch(
        "world_bank.pipelines.dimensions.latest_source_file", return_value=income_file
    )
    mocker.patch(
        "world_bank.pipelines.dimensions.read_latest_load",
        side_effect=lambda _conn, endpoint: _load(endpoint),
    )
    upsert = mocker.patch("world_bank.pipelines.dimensions.upsert_rows", return_value=1)
    mocker.patch("world_bank.pipelines.dimensions.delete_missing_links", return_value=0)
    settings = MagicMock(indicators=["AA"])

    results = run_dimensions(MagicMock(), settings)

    assert [r.table for r in results] == WRITE_ORDER
    assert [c.args[1] for c in upsert.call_args_list] == WRITE_ORDER


def test_missing_indicator_in_bronze_writes_nothing(mocker: MockerFixture) -> None:
    mocker.patch(
        "world_bank.pipelines.dimensions.read_latest_load",
        side_effect=lambda _conn, endpoint: (
            None if endpoint == "indicator/AA" else _load(endpoint)
        ),
    )
    upsert = mocker.patch("world_bank.pipelines.dimensions.upsert_rows")
    settings = MagicMock(indicators=["AA"])

    with pytest.raises(SchemaValidationError, match="rode load-bronze"):
        run_dimensions(MagicMock(), settings)

    upsert.assert_not_called()


def test_missing_income_history_in_bronze_writes_nothing(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "world_bank.pipelines.dimensions.read_latest_load",
        side_effect=lambda _conn, endpoint: _load(endpoint),
    )
    mocker.patch(
        "world_bank.pipelines.dimensions.latest_source_file", return_value=None
    )
    upsert = mocker.patch("world_bank.pipelines.dimensions.upsert_rows")

    with pytest.raises(SchemaValidationError, match="histórico de renda"):
        run_dimensions(MagicMock(), MagicMock(indicators=["AA"]))

    upsert.assert_not_called()


def test_invalid_record_writes_nothing(
    mocker: MockerFixture, income_file: SourceFile
) -> None:
    mocker.patch(
        "world_bank.pipelines.dimensions.latest_source_file", return_value=income_file
    )

    def read(_conn: MagicMock, endpoint: str) -> BronzeLoad:
        if endpoint == "topic":
            return BronzeLoad(endpoint, uuid4(), [{"id": "x", "value": "Tema"}])
        return _load(endpoint)

    mocker.patch("world_bank.pipelines.dimensions.read_latest_load", side_effect=read)
    upsert = mocker.patch("world_bank.pipelines.dimensions.upsert_rows")

    with pytest.raises(SchemaValidationError, match="inteiro inválido"):
        run_dimensions(MagicMock(), MagicMock(indicators=["AA"]))

    upsert.assert_not_called()
