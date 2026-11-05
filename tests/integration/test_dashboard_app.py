"""Cada tela do Streamlit abre contra a gold real, sem erro, e mostra os números.

Fica fora do ``pytest`` padrão. Para rodar:
``uv run --group dashboard pytest -m integration --no-cov``.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.integration

RAIZ = Path(__file__).resolve().parents[2]


def _dashboard_url() -> str:
    for line in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DASHBOARD_DATABASE_URL="):
            return line.removeprefix("DASHBOARD_DATABASE_URL=").strip()
    pytest.skip("DASHBOARD_DATABASE_URL não definida no .env")


@pytest.fixture(autouse=True)
def ambiente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DASHBOARD_DATABASE_URL", _dashboard_url())
    monkeypatch.setenv("DATABASE_URL", "postgresql://nao_usado@127.0.0.1/nada")
    monkeypatch.syspath_prepend(str(RAIZ / "dashboard"))
    monkeypatch.chdir(RAIZ)
    yield
    sys.modules.pop("paginas", None)


def _abrir(pagina: str):
    testing = pytest.importorskip("streamlit.testing.v1")
    fonte = f"import paginas\npaginas.{pagina}()\n"
    app = testing.AppTest.from_string(fonte, default_timeout=60).run()
    assert not app.exception, [e.value for e in app.exception]
    return app


def _um_valor(sql: str):
    with psycopg.connect(_dashboard_url()) as conn:
        linha = conn.execute(sql).fetchone()
    assert linha is not None
    return linha[0]


def test_tela_de_renda_conta_os_paises_analisados() -> None:
    app = _abrir("renda_e_vida")

    total = _um_valor(
        "select paises_com_valor from gold.resumo_renda_regiao where recorte = 'mundo'"
        " and indicador_id = 'SP.DYN.LE00.IN' and ano = 2023"
    )
    assert app.metric[0].value.startswith(f"{total} de ")


def test_tela_de_renda_mostra_a_diferenca_da_gold() -> None:
    app = _abrir("renda_e_vida")

    diferenca = _um_valor(
        "select max(mediana) filter (where nivel_renda_id = 'HIC')"
        " - max(mediana) filter (where nivel_renda_id = 'LIC')"
        " from gold.resumo_renda_regiao where recorte = 'renda'"
        " and indicador_id = 'SP.DYN.LE00.IN' and ano = 2023"
    )
    assert app.metric[1].value == f"{diferenca:.1f} anos".replace(".", ",")


def test_tela_de_pib_mostra_a_posicao_do_brasil_na_gold() -> None:
    app = _abrir("pib_e_crescimento")

    posicao = _um_valor(
        "select posicao_pib_mundo from gold.ranking_crescimento where pais_iso3 = 'BRA'"
    )
    assert app.metric[3].value == f"{posicao}º"


def test_tela_de_renda_troca_de_ano_sem_erro() -> None:
    app = _abrir("renda_e_vida")
    app.selectbox[0].select(2010).run()

    assert not app.exception


def test_tela_de_pib_mostra_o_periodo_do_ranking() -> None:
    app = _abrir("pib_e_crescimento")

    fim = _um_valor("select max(ano_final) from gold.ranking_crescimento")
    assert any(f"de {fim - 10} a {fim}" in s.value for s in app.subheader)


def test_tela_de_pib_filtra_por_regiao_e_sem_paises() -> None:
    app = _abrir("pib_e_crescimento")
    app.selectbox[1].select("Sul da Ásia").run()
    app.multiselect[0].set_value([]).run()

    assert not app.exception


def test_tela_de_pib_troca_o_ano_sem_erro() -> None:
    app = _abrir("pib_e_crescimento")
    app.selectbox[0].select(2005).run()

    assert not app.exception
