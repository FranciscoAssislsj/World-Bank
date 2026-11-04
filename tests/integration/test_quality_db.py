"""Regras de qualidade contra o PostgreSQL real, com a silver já carregada.

Ficam fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
O dado ruim é plantado numa transação desfeita no fim: nada fica gravado.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest

from world_bank.exceptions import QualityCheckError
from world_bank.extract.client import ApiPage
from world_bank.load.postgres import apply_migrations, insert_pages, list_migrations
from world_bank.pipelines.observations import run_observations
from world_bank.validate.checks import check_params, load_checks, run_check

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _database_url() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.removeprefix("DATABASE_URL=").strip()
    pytest.skip("DATABASE_URL não definida no .env")


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_database_url(), autocommit=True) as connection:
        apply_migrations(connection, list_migrations())
        row = connection.execute("select count(*) from silver.fato_observacao")
        if row.fetchone()[0] == 0:
            pytest.skip("silver sem dados: rode as cargas antes")
        yield connection


@pytest.fixture
def params(conn: psycopg.Connection) -> dict[str, Any]:
    """Parâmetros do período carregado, com os indicadores da requisição real."""
    endpoint = conn.execute(
        "select endpoint from bronze.api_response"
        " where endpoint like 'country/all/indicator/%%' and params ->> 'date' = %s"
        " limit 1",
        ("2000:2024",),
    ).fetchone()[0]
    indicators = endpoint.removeprefix("country/all/indicator/").split(";")
    return check_params(indicators, 2000, 2024)


def _run(conn: psycopg.Connection, name: str, params: dict[str, Any]) -> Any:
    check = next(c for c in load_checks() if c.name == name)
    return run_check(conn, check, params)


def test_every_rule_runs_and_error_rules_pass_on_real_data(
    conn: psycopg.Connection, params: dict[str, Any]
) -> None:
    results = [run_check(conn, check, params) for check in load_checks()]

    assert len(results) == 16
    assert [r.name for r in results if r.severity == "error" and not r.passed] == []


UPDATE = (
    "update silver.fato_observacao set valor = {value}"
    " where pais_iso3 = 'BRA' and indicador_id = '{indicator}' and ano = 2023"
)


@pytest.mark.parametrize(
    ("rule", "statement"),
    [
        ("faixa_percentual", UPDATE.format(value=150, indicator="SP.URB.TOTL.IN.ZS")),
        ("faixa_positivo", UPDATE.format(value=-1, indicator="SP.POP.TOTL")),
        (
            "faixa_nao_negativo",
            UPDATE.format(value=-1, indicator="EN.GHG.CO2.PC.CE.AR5"),
        ),
        (
            "faixa_expectativa_vida",
            UPDATE.format(value=200, indicator="SP.DYN.LE00.IN"),
        ),
        ("fato_diverge_bronze", UPDATE.format(value=1, indicator="NY.GDP.MKTP.CD")),
        (
            "faixa_ano",
            "update silver.fato_observacao set ano = 1900"
            " where pais_iso3 = 'BRA' and indicador_id = 'SP.POP.TOTL' and ano = 2023",
        ),
        (
            "completude_fato",
            "delete from silver.fato_observacao"
            " where pais_iso3 = 'BRA' and indicador_id = 'SP.POP.TOTL' and ano = 2023",
        ),
    ],
)
def test_error_rule_catches_planted_problem(
    conn: psycopg.Connection, params: dict[str, Any], rule: str, statement: str
) -> None:
    with conn.transaction(force_rollback=True):
        assert _run(conn, rule, params).passed
        conn.execute(statement)

        result = _run(conn, rule, params)

        assert not result.passed
        assert result.rows_failed >= 1
        assert result.sample


def test_bronze_rule_catches_incomplete_load(
    conn: psycopg.Connection,
    params: dict[str, Any],
    make_api_page: Callable[..., ApiPage],
) -> None:
    page = make_api_page(path=f"teste/{uuid4()}", page=1, pages=2)

    with conn.transaction(force_rollback=True):
        insert_pages(conn, uuid4(), [page])

        assert not _run(conn, "bronze_completa", params).passed


def test_warning_rule_shows_planted_outlier(
    conn: psycopg.Connection, params: dict[str, Any]
) -> None:
    with conn.transaction(force_rollback=True):
        before = _run(conn, "valor_atipico", params).rows_failed
        conn.execute(UPDATE.format(value=5, indicator="SP.DYN.LE00.IN"))

        assert _run(conn, "valor_atipico", params).rows_failed == before + 1


def test_impossible_value_is_not_published_and_result_stays_recorded(
    conn: psycopg.Connection, make_api_page: Callable[..., ApiPage]
) -> None:
    indicator = "SP.URB.TOTL.IN.ZS"
    record = {
        "indicator": {"id": indicator},
        "country": {"id": "BR"},
        "date": "1990",
        "value": 150,
        "decimal": 1,
    }
    page = make_api_page(
        path=f"country/all/indicator/{indicator}",
        records=[record],
        params={"date": "1990:1990"},
    )

    with conn.transaction(force_rollback=True):
        insert_pages(conn, uuid4(), [page])

        with pytest.raises(QualityCheckError, match="faixa_percentual"):
            run_observations(conn, MagicMock(indicators=[indicator]), 1990, 1990)

        published = conn.execute(
            "select count(*) from silver.fato_observacao where ano = 1990"
        ).fetchone()
        run = conn.execute(
            "select r.status, c.passed from etl.pipeline_run r"
            " join etl.quality_check c using (run_id)"
            " where r.params ->> 'period' = '1990:1990'"
            " and c.check_name = 'faixa_percentual'"
        ).fetchone()
        assert published == (0,)
        assert run == ("failed", False)
