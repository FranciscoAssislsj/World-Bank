"""O projeto do Power BI é texto: dá para conferir suas regras sem abrir o programa."""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from world_bank.load.gold import load_views

RAIZ = Path(__file__).resolve().parents[2] / "dashboard" / "powerbi"
TABELAS = RAIZ / "world_bank.SemanticModel" / "definition" / "tables"
RELATORIO = RAIZ / "world_bank.Report" / "definition"
CONSULTA = re.compile(r'Value\.NativeQuery\(Fonte, "(?P<sql>[^"]+)"\)')
COLUNA = re.compile(r"^\tcolumn (\S+)$", re.MULTILINE)
MEDIDA = re.compile(r"^\tmeasure '([^']+)'", re.MULTILINE)


def _modelo() -> dict[str, set[str]]:
    """Os campos de cada tabela do modelo, colunas e medidas juntas."""
    campos = {}
    for arquivo in TABELAS.glob("*.tmdl"):
        texto = arquivo.read_text(encoding="utf-8")
        campos[arquivo.stem] = set(COLUNA.findall(texto)) | set(MEDIDA.findall(texto))
    return campos


def _referencias(no: Any) -> Iterator[tuple[str, str]]:
    """Cada par (tabela, campo) citado em um arquivo do relatório."""
    if isinstance(no, list):
        for item in no:
            yield from _referencias(item)
    elif isinstance(no, dict):
        fonte = no.get("Expression", {}) if "Property" in no else {}
        if "Entity" in fonte.get("SourceRef", {}):
            yield fonte["SourceRef"]["Entity"], no["Property"]
        for valor in no.values():
            yield from _referencias(valor)


def _visuais() -> list[Path]:
    return sorted(RELATORIO.glob("pages/*/visuals/*/visual.json"))


def test_each_query_reads_only_gold_columns_that_exist() -> None:
    colunas = {view.name: view.columns.keys() for view in load_views()}
    consultas = 0
    for arquivo in TABELAS.glob("*.tmdl"):
        for achado in CONSULTA.finditer(arquivo.read_text(encoding="utf-8")):
            consultas += 1
            sql = achado["sql"]
            origens = re.findall(r"\b(?:from|join)\s+([\w.]+)", sql, re.IGNORECASE)
            assert origens == [f"gold.{arquivo.stem}"]  # só gold (D-078)
            lista = re.search(r"select (.+?) from ", sql, re.IGNORECASE)
            assert lista is not None
            pedidas = {c.strip() for c in lista[1].split(",")}
            assert pedidas <= colunas[arquivo.stem]

    assert consultas == 4


def test_model_columns_are_the_ones_each_query_returns() -> None:
    for arquivo in TABELAS.glob("*.tmdl"):
        texto = arquivo.read_text(encoding="utf-8")
        achado = CONSULTA.search(texto)
        if achado is None:
            continue
        lista = re.search(r"select (.+?) from ", achado["sql"], re.IGNORECASE)
        assert lista is not None
        assert set(COLUNA.findall(texto)) == {c.strip() for c in lista[1].split(",")}


def test_measures_never_read_other_layers_or_invent_rules() -> None:
    texto = (TABELAS / "Medidas.tmdl").read_text(encoding="utf-8")

    # As medidas só escolhem um valor que a gold já traz e o escrevem (D-097).
    assert "silver" not in texto
    formulas = re.sub(r'"[^"]*"', '""', texto)  # sem os textos entre aspas
    formulas = re.sub(r"^\t+(lineageTag|formatString):.*$", "", formulas, flags=re.M)
    assert not re.search(r"[-+*/]", formulas), "operação aritmética"
    proibidas = (
        r"\b(SUM|SUMX|AVERAGE|COUNT|COUNTROWS|MIN|MINX|MAX|MAXX|DIVIDE|TOPN|RANKX)\("
    )
    assert not re.search(proibidas, formulas)


def test_visuals_never_summarize_or_rank() -> None:
    """Sem soma automática nem filtro Top N: o gráfico mostra o valor da gold."""
    for arquivo in _visuais():
        texto = arquivo.read_text(encoding="utf-8")
        assert '"Aggregation"' not in texto, arquivo.parent.name
        assert '"TopN"' not in texto, arquivo.parent.name


def test_every_field_used_by_a_visual_exists_in_the_model() -> None:
    modelo = _modelo()
    assert _visuais()

    faltando = sorted(
        {
            f"{arquivo.parent.name}: {tabela}.{campo}"
            for arquivo in _visuais()
            for tabela, campo in _referencias(
                json.loads(arquivo.read_text(encoding="utf-8"))
            )
            if campo not in modelo.get(tabela, set())
        }
    )

    assert faltando == []


def test_pages_have_their_declared_folder_and_visual_names() -> None:
    paginas = json.loads((RELATORIO / "pages" / "pages.json").read_text("utf-8"))

    assert paginas["pageOrder"] == ["renda_e_vida", "pib_e_crescimento"]
    for arquivo in _visuais():
        visual = json.loads(arquivo.read_text(encoding="utf-8"))
        assert visual["name"] == arquivo.parent.name


def test_interactions_point_to_visuals_of_the_same_page() -> None:
    for nome in ("renda_e_vida", "pib_e_crescimento"):
        pasta = RELATORIO / "pages" / nome
        pagina = json.loads((pasta / "page.json").read_text(encoding="utf-8"))
        existentes = {p.name for p in (pasta / "visuals").iterdir()}
        for regra in pagina.get("visualInteractions", []):
            assert {regra["source"], regra["target"]} <= existentes


def test_each_page_has_its_background_image_in_the_project() -> None:
    """O fundo vem do Figma, e a imagem precisa ter o tamanho da página (D-089)."""
    recursos = RAIZ / "world_bank.Report" / "StaticResources" / "RegisteredResources"
    for nome in ("renda_e_vida", "pib_e_crescimento"):
        pagina = json.loads(
            (RELATORIO / "pages" / nome / "page.json").read_text(encoding="utf-8")
        )
        imagem = recursos / f"fundo_{nome}.png"
        assert f"fundo_{nome}.png" in json.dumps(pagina["objects"]["background"])
        # Num PNG, a largura e a altura ficam nos bytes 16 a 24 do arquivo.
        cabecalho = imagem.read_bytes()[16:24]
        largura = int.from_bytes(cabecalho[:4], "big")
        altura = int.from_bytes(cabecalho[4:], "big")
        assert (largura, altura) == (pagina["width"], pagina["height"])


@pytest.mark.parametrize("segredo", ["password", "senha", "pwd=", "dashboard_leitor"])
def test_project_has_no_credentials(segredo: str) -> None:
    arquivos = [
        p
        for p in RAIZ.rglob("*")
        if p.is_file() and ".pbi" not in p.parts and p.suffix != ".png"
    ]
    assert arquivos

    com_segredo = [
        p.name for p in arquivos if segredo in p.read_text(encoding="utf-8").lower()
    ]

    assert com_segredo == []
