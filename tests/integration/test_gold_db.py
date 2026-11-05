"""Views da gold contra o PostgreSQL real, com a silver já carregada.

Ficam fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
O dado é plantado numa transação desfeita no fim: nada fica gravado.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest

from world_bank.exceptions import LoadError
from world_bank.load.gold import load_views, rebuild_views
from world_bank.load.postgres import apply_migrations, list_migrations
from world_bank.validate.checks import load_checks, run_check

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
CO2 = "EN.GHG.CO2.PC.CE.AR5"
POP = "SP.POP.TOTL"
GDP_GROWTH = "NY.GDP.MKTP.KD.ZG"


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
        with connection.transaction(force_rollback=True):
            yield connection


def _set(conn: psycopg.Connection, country: str, indicator: str, year: int, value: Any):
    conn.execute(
        "update silver.fato_observacao set valor = %s"
        " where pais_iso3 = %s and indicador_id = %s and ano = %s",
        (value, country, indicator, year),
    )


def _build(conn: psycopg.Connection) -> dict[str, int]:
    return rebuild_views(conn, load_views())


def _one(conn: psycopg.Connection, query: str, *params: Any) -> tuple[Any, ...]:
    return conn.execute(query, params).fetchone()


def test_every_file_runs_alone_as_a_query(conn: psycopg.Connection) -> None:
    for view in load_views():
        conn.execute(f"select * from ({view.query}) as q limit 1")  # noqa: S608


def test_pais_ano_has_only_countries(conn: psycopg.Connection) -> None:
    _build(conn)

    assert _one(
        conn,
        "select count(*) from gold.pais_ano g"
        " join silver.dim_pais p using (pais_iso3) where p.e_agregado",
    ) == (0,)


def test_pais_ano_income_follows_the_year(conn: psycopg.Connection) -> None:
    conn.execute(
        "update silver.classificacao_renda_anual set nivel_renda_id = %s"
        " where pais_iso3 = 'BRA' and ano_referencia = 2001",
        ("LIC",),
    )
    conn.execute(
        "update silver.classificacao_renda_anual set nivel_renda_id = %s"
        " where pais_iso3 = 'BRA' and ano_referencia = 2002",
        ("HIC",),
    )
    _build(conn)

    rows = conn.execute(
        "select nivel_renda_id from gold.pais_ano"
        " where pais_iso3 = 'BRA' and ano in (2001, 2002) order by ano"
    ).fetchall()

    assert rows == [("LIC",), ("HIC",)]


def test_resumo_calculates_each_cut_for_a_planted_group(
    conn: psycopg.Connection,
) -> None:
    conn.execute(
        "update silver.fato_observacao f set valor = null from silver.dim_pais p"
        " where p.pais_iso3 = f.pais_iso3 and f.indicador_id = %s and f.ano = 2005"
        " and not p.e_agregado",
        ("SP.URB.TOTL.IN.ZS",),
    )
    for country, value in (("BRA", 10), ("ARG", 20), ("CHL", 60)):
        _set(conn, country, "SP.URB.TOTL.IN.ZS", 2005, value)
    _build(conn)

    row = _one(
        conn,
        "select round(media, 4), round(mediana, 4), paises_com_valor, paises_no_grupo,"
        " cobertura_baixa from gold.resumo_renda_regiao where recorte = 'regiao'"
        " and regiao_id = 'LCN' and indicador_id = 'SP.URB.TOTL.IN.ZS' and ano = 2005",
    )
    world = _one(
        conn,
        "select round(media, 4), paises_com_valor from gold.resumo_renda_regiao"
        " where recorte = 'mundo' and indicador_id = 'SP.URB.TOTL.IN.ZS'"
        " and ano = 2005",
    )

    assert row[:3] == (30, 20, 3)
    assert row[3] == 42
    assert row[4] is True
    assert world == (30, 3)


def test_resumo_has_exactly_four_cuts_and_no_row_without_income_in_income_cuts(
    conn: psycopg.Connection,
) -> None:
    _build(conn)

    cuts = conn.execute(
        "select distinct recorte from gold.resumo_renda_regiao order by 1"
    ).fetchall()
    orphans = _one(
        conn,
        "select count(*) from gold.resumo_renda_regiao"
        " where recorte in ('renda', 'renda_regiao') and nivel_renda_id is null",
    )

    assert cuts == [("mundo",), ("regiao",), ("renda",), ("renda_regiao",)]
    assert orphans == (0,)


def test_value_over_the_limit_leaves_analysis_but_stays_in_silver_and_sum(
    conn: psycopg.Connection,
) -> None:
    _set(conn, "BRA", CO2, 2010, 500)
    _set(conn, "BRA", POP, 2010, None)
    _build(conn)

    row = _one(
        conn,
        "select co2_per_capita, valores_removidos, motivo_remocao from gold.pais_ano"
        " where pais_iso3 = 'BRA' and ano = 2010",
    )
    summary = _one(
        conn,
        "select valores_removidos, media < 100 from gold.resumo_renda_regiao"
        " where recorte = 'regiao' and regiao_id = 'LCN' and indicador_id = %s"
        " and ano = 2010",
        CO2,
    )
    warning = _one(
        conn,
        "select valor_original, sai_da_analise from gold.valores_atipicos"
        " where pais_iso3 = 'BRA' and indicador_id = %s and ano = 2010",
        CO2,
    )
    silver = _one(
        conn,
        "select valor from silver.fato_observacao"
        " where pais_iso3 = 'BRA' and indicador_id = %s and ano = 2010",
        CO2,
    )

    assert row[0] is None
    assert row[1] == 1
    assert "CO2" in row[2]
    assert summary == (1, True)
    assert warning == (500, True)
    assert silver == (500,)


def test_population_jump_stays_in_analysis_and_leaves_only_the_urban_ranking(
    conn: psycopg.Connection,
) -> None:
    _set(conn, "BRA", POP, 2020, 900_000_000)
    _build(conn)

    row = _one(
        conn,
        "select populacao from gold.pais_ano where pais_iso3 = 'BRA' and ano = 2020",
    )
    ranking = _one(
        conn,
        "select crescimento_populacao_urbana_pct, posicao_populacao_urbana_mundo,"
        " motivo_remocao, crescimento_pib_real_pct is not null"
        " from gold.ranking_crescimento where pais_iso3 = 'BRA'",
    )
    removed = _one(
        conn,
        "select bool_or(sai_da_analise) from gold.valores_atipicos"
        " where pais_iso3 = 'BRA' and indicador_id = %s",
        POP,
    )

    assert row == (900_000_000,)
    assert ranking[0] is None
    assert ranking[1] is None
    assert "população" in ranking[2]
    assert ranking[3] is True
    assert removed == (False,)


def test_population_jump_outside_the_window_keeps_the_country_in_ranking(
    conn: psycopg.Connection,
) -> None:
    _build(conn)

    assert _one(
        conn,
        "select crescimento_populacao_urbana_pct is not null, motivo_remocao"
        " from gold.ranking_crescimento where pais_iso3 = 'QAT'",
    ) == (True, None)


def test_ranking_compounds_growth_and_requires_every_year(
    conn: psycopg.Connection,
) -> None:
    for year in range(2015, 2025):
        _set(conn, "BRA", GDP_GROWTH, year, 10)
    _set(conn, "ARG", GDP_GROWTH, 2018, None)
    _build(conn)

    brazil = _one(
        conn,
        "select round(crescimento_pib_real_pct, 4), ano_inicial, ano_final,"
        " posicao_pib_mundo is not null"
        " from gold.ranking_crescimento where pais_iso3 = 'BRA'",
    )
    argentina = _one(
        conn,
        "select crescimento_pib_real_pct, posicao_pib_regiao, posicao_pib_mundo"
        " from gold.ranking_crescimento where pais_iso3 = 'ARG'",
    )

    assert float(brazil[0]) == pytest.approx(159.3742, abs=0.001)
    assert brazil[1:] == (2014, 2024, True)
    assert argentina == (None, None, None)


def test_reconciliation_detects_a_planted_difference(conn: psycopg.Connection) -> None:
    _set(conn, "NAC", POP, 2015, 1)
    _build(conn)

    row = _one(
        conn,
        "select dentro_da_tolerancia, valor_oficial from gold.reconciliacao_agregados"
        " where agregado_id = 'NAC' and indicador_id = %s and ano = 2015",
        POP,
    )
    other = _one(
        conn,
        "select dentro_da_tolerancia from gold.reconciliacao_agregados"
        " where agregado_id = 'NAC' and indicador_id = %s and ano = 2016",
        POP,
    )

    assert row == (False, 1)
    assert other == (True,)


def test_error_in_the_middle_keeps_previous_views(conn: psycopg.Connection) -> None:
    _build(conn)
    before = _one(conn, "select count(*) from gold.pais_ano")
    views = load_views()
    broken = [*views[:-1], replace(views[-1], query="select * from nao_existe")]

    with pytest.raises(LoadError, match="recriar a gold"):
        rebuild_views(conn, broken)

    assert _one(conn, "select count(*) from gold.pais_ano") == before


def test_view_removed_from_folder_is_dropped(conn: psycopg.Connection) -> None:
    _build(conn)

    rebuild_views(conn, [v for v in load_views() if v.name != "ranking_crescimento"])

    assert _one(
        conn,
        "select count(*) from pg_matviews where schemaname = 'gold'"
        " and matviewname = 'ranking_crescimento'",
    ) == (0,)


def test_quality_rule_reads_the_single_definition(conn: psycopg.Connection) -> None:
    check = next(c for c in load_checks() if c.name == "valor_atipico")
    total = _one(conn, "select count(*) from silver.valor_atipico")

    assert run_check(conn, check, {}).rows_failed == total[0]


def test_every_column_has_a_comment(conn: psycopg.Connection) -> None:
    _build(conn)

    missing = conn.execute(
        """
        select c.relname, a.attname
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        join pg_attribute a on a.attrelid = c.oid and a.attnum > 0
        where n.nspname = 'gold' and c.relkind = 'm'
          and col_description(c.oid, a.attnum) is null
        """
    ).fetchall()

    assert missing == []
