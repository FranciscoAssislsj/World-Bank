from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import pytest

from world_bank.config import load_settings
from world_bank.exceptions import ConfigurationError, LoadError
from world_bank.load.gold import (
    GOLD_DIR,
    GoldView,
    count_values_out_of_mean,
    load_views,
    parse_view,
    rebuild_views,
)

HEADER = """-- gold.exemplo
-- Pergunta de negócio: Quanto?
-- Grão (o que é uma linha): um país.
-- Origem: silver.dim_pais
-- Regras: nenhuma (D-000).
-- Chave: pais_iso3, ano
-- Coluna pais_iso3: Código.
-- Coluna ano: Ano.
"""


def test_parse_view_reads_header_and_query() -> None:
    view = parse_view("exemplo", HEADER + "select 1 as pais_iso3, 2 as ano;\n")

    assert view.name == "exemplo"
    assert view.key == ("pais_iso3", "ano")
    assert view.columns == {"pais_iso3": "Código.", "ano": "Ano."}
    assert view.query == "select 1 as pais_iso3, 2 as ano"
    assert "Quanto?" in view.description
    assert "um país." in view.description


def test_parse_view_accepts_with_and_windows_line_endings() -> None:
    query = "with a as (select 1) select * from a;\n"
    text = (HEADER + query).replace("\n", "\r\n")

    assert parse_view("exemplo", text).query.startswith("with a")


def test_parse_view_allows_semicolon_inside_text_and_comments() -> None:
    query = "select 'a; b' as x -- comentário; com ponto e vírgula\nfrom t;"

    assert "a; b" in parse_view("exemplo", HEADER + query).query


def test_parse_view_rejects_first_line_with_other_name() -> None:
    with pytest.raises(ConfigurationError, match="primeira linha"):
        parse_view("outro", HEADER + "select 1;")


@pytest.mark.parametrize(
    "line",
    [
        "-- Pergunta de negócio: Quanto?\n",
        "-- Grão (o que é uma linha): um país.\n",
        "-- Origem: silver.dim_pais\n",
        "-- Regras: nenhuma (D-000).\n",
        "-- Chave: pais_iso3, ano\n",
    ],
)
def test_parse_view_rejects_incomplete_header(line: str) -> None:
    with pytest.raises(ConfigurationError, match="cabeçalho sem"):
        parse_view("exemplo", HEADER.replace(line, "") + "select 1;")


def test_parse_view_rejects_header_without_columns() -> None:
    text = HEADER.replace("-- Coluna pais_iso3: Código.\n", "").replace(
        "-- Coluna ano: Ano.\n", ""
    )

    with pytest.raises(ConfigurationError, match="colunas"):
        parse_view("exemplo", text + "select 1;")


@pytest.mark.parametrize(
    "body",
    ["", "create materialized view gold.exemplo as select 1;", "drop table x;"],
)
def test_parse_view_rejects_body_that_is_not_a_query(body: str) -> None:
    with pytest.raises(ConfigurationError, match="select ou with"):
        parse_view("exemplo", HEADER + body)


def test_parse_view_rejects_two_statements() -> None:
    with pytest.raises(ConfigurationError, match="uma query"):
        parse_view("exemplo", HEADER + "select 1; drop table x;")


def test_load_views_reads_directory_in_name_order(tmp_path: Path) -> None:
    for name in ("b", "a"):
        text = HEADER.replace("gold.exemplo", f"gold.{name}") + "select 1;"
        (tmp_path / f"{name}.sql").write_text(text, encoding="utf-8")

    assert [view.name for view in load_views(tmp_path)] == ["a", "b"]


def test_load_views_fails_on_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="nenhuma view"):
        load_views(tmp_path)


def test_project_files_are_valid_and_read_only_silver() -> None:
    views = load_views()

    assert {view.name for view in views} == {
        "pais_ano",
        "ranking_crescimento",
        "reconciliacao_agregados",
        "resumo_renda_regiao",
        "valores_atipicos",
    }
    for view in views:
        assert " gold." not in view.query  # cada view lê só a silver (D-057)
        assert set(view.key) <= view.columns.keys()


def test_every_configured_indicator_is_a_column_of_pais_ano() -> None:
    configs = GOLD_DIR.parents[1] / "configs"
    settings = load_settings(config_dir=configs)
    text = (GOLD_DIR / "pais_ano.sql").read_text(encoding="utf-8")

    missing = [code for code in settings.indicators if f"'{code}'" not in text]

    assert missing == []


def _view(name: str = "a") -> GoldView:
    return GoldView(name, "descrição", ("x",), {"x": "coluna"}, "select 1 as x")


def _conn(columns: list[str] | None = None, rows: int = 3) -> MagicMock:
    """Conexão falsa: responde ao catálogo, às colunas criadas e à contagem."""
    conn = MagicMock()

    def execute(query: object, params: object = None) -> MagicMock:
        cursor = MagicMock()
        text = query if isinstance(query, str) else ""
        if "pg_matviews" in text:
            cursor.fetchall.return_value = [("velha",)]
        elif "pg_attribute" in text:
            cursor.fetchall.return_value = [(c,) for c in (columns or ["x"])]
        else:
            cursor.fetchone.return_value = (rows,)
        return cursor

    conn.execute.side_effect = execute
    return conn


def test_rebuild_views_drops_old_views_and_counts_rows() -> None:
    conn = _conn()

    assert rebuild_views(conn, [_view()]) == {"a": 3}

    statements = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert any("drop materialized view" in s and "velha" in s for s in statements)
    assert any("create materialized view" in s for s in statements)
    assert any("create unique index" in s for s in statements)
    conn.transaction.assert_called_once()


def test_rebuild_views_fails_when_a_view_is_empty() -> None:
    with pytest.raises(LoadError, match="vazias"):
        rebuild_views(_conn(rows=0), [_view()])


def test_rebuild_views_fails_when_a_column_has_no_description() -> None:
    with pytest.raises(LoadError, match="sem descrição"):
        rebuild_views(_conn(columns=["x", "y"]), [_view()])


def test_rebuild_views_turns_database_error_into_load_error() -> None:
    conn = MagicMock()
    conn.execute.side_effect = psycopg.errors.SyntaxError("erro")

    with pytest.raises(LoadError, match="recriar a gold"):
        rebuild_views(conn, [_view()])


def test_count_values_out_of_mean_reads_the_warning_view() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (27,)

    assert count_values_out_of_mean(conn) == 27
