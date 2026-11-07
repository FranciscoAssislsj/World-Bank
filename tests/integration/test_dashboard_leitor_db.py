"""O usuário dos dashboards só consegue ler a gold (D-079), contra o banco real.

Fica fora do ``pytest`` padrão. Para rodar: ``uv run pytest -m integration``.
"""

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from world_bank.load.gold import load_views, rebuild_views
from world_bank.load.postgres import apply_migrations, list_migrations

pytestmark = pytest.mark.integration

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _env(name: str) -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.removeprefix(f"{name}=").strip()
    pytest.skip(f"{name} não definida no .env")


@pytest.fixture
def leitor() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_env("DASHBOARD_DATABASE_URL"), autocommit=True) as connection:
        yield connection


@pytest.mark.parametrize(
    ("view", "coluna_codigo", "coluna_nome", "categoria"),
    [
        ("pais_ano", "pais_iso3", "pais", "pais"),
        ("pais_ano", "regiao_id", "regiao", "regiao"),
        ("pais_ano", "nivel_renda_id", "nivel_renda", "renda"),
        ("resumo_renda_regiao", "indicador_id", "indicador", "indicador"),
        ("reconciliacao_agregados", "agregado_id", "agregado", "agregado"),
    ],
)
def test_todo_nome_da_gold_tem_traducao(
    view: str, coluna_codigo: str, coluna_nome: str, categoria: str
) -> None:
    """Um código novo da API sem tradução apareceria em inglês na tela (D-082)."""
    with psycopg.connect(_env("DATABASE_URL")) as dono:
        faltando = dono.execute(
            f"""
            select distinct g.{coluna_codigo}, g.{coluna_nome}
            from gold.{view} g
            left join silver.nome_portugues n
                on n.categoria = %s and n.codigo = g.{coluna_codigo}
            where g.{coluna_codigo} is not null and n.codigo is null
            """,  # noqa: S608
            (categoria,),
        ).fetchall()

    assert faltando == []


def test_le_a_gold(leitor: psycopg.Connection) -> None:
    row = leitor.execute("select count(*) from gold.pais_ano").fetchone()

    assert row is not None
    assert row[0] > 0


@pytest.mark.parametrize(
    "tabela", ["silver.observacao", "bronze.api_response", "etl.pipeline_run"]
)
def test_nao_le_outras_camadas(leitor: psycopg.Connection, tabela: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        leitor.execute(f"select 1 from {tabela} limit 1")  # noqa: S608


@pytest.mark.parametrize(
    "comando",
    [
        "create table gold.teste (id int)",
        "create table public.teste (id int)",
        "refresh materialized view gold.pais_ano",
        "drop materialized view gold.pais_ano",
    ],
)
def test_nao_escreve(leitor: psycopg.Connection, comando: str) -> None:
    erros = (
        psycopg.errors.InsufficientPrivilege,
        psycopg.errors.ReadOnlySqlTransaction,
    )
    with pytest.raises(erros):
        leitor.execute(comando)


def test_permissao_sobrevive_ao_build_gold() -> None:
    """O ``build-gold`` recria as views; o leitor precisa continuar lendo todas."""
    with psycopg.connect(_env("DATABASE_URL"), autocommit=True) as dono:
        apply_migrations(dono, list_migrations())
        views = load_views()
        with dono.transaction(force_rollback=True):
            rebuild_views(dono, views)
            for view in views:
                row = dono.execute(
                    "select has_table_privilege('dashboard_leitor', %s, 'select')",
                    (f"gold.{view.name}",),
                ).fetchone()
                assert row == (True,), view.name
