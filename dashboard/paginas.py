"""As duas telas do dashboard (D-083), contadas a partir do Brasil (D-084).

Aqui só se desenha: todo número vem pronto de ``world_bank.dashboard.consultas``, que lê
a gold. O que muda neste arquivo é a escrita de um número, nunca o valor (D-078).
As poucas contas daqui são só de desenho, como a altura de um rótulo ou o tamanho
máximo da bolha, e nenhuma vira número na tela (D-097).
"""

from typing import Any

import altair as alt
import streamlit as st

from world_bank.config import load_settings
from world_bank.dashboard import consultas as q
from world_bank.dashboard.formato import indicador, numero
from world_bank.exceptions import LoadError

TODAS = "Todas"
BRASIL = "Brasil"
FONTE = "Source Sans, sans-serif"
TINTA, TINTA2 = "#0b0b0b", "#52514e"
GRADE, EIXO = "#e1e0d9", "#c3c2b7"
# A cor conta a história: laranja é sempre o Brasil, e cinza é o contexto (D-084).
DESTAQUE, CONTEXTO, QUEDA = "#eb6834", "#a9b0b8", "#d03b3b"
CRITICO = "#d03b3b"
# Sem o laranja, reservado ao Brasil. A ordem é fixa e conferida para daltonismo.
CORES_PAISES = [
    "#2a78d6",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#6250d6",
    "#73787e",
]
PAISES_PADRAO = ["Estados Unidos", "China", BRASIL]
# Cor por faixa de renda: um só tom, do claro ao escuro, porque as faixas têm ordem.
CORES_RENDA = {
    "Não classificado": "#c3c2b7",
    "Renda baixa": "#86b6ef",
    "Renda média-baixa": "#3987e5",
    "Renda média-alta": "#1c5cab",
    "Renda alta": "#0d366b",
}


@st.cache_resource
def _url() -> str | None:
    url = load_settings().dashboard_database_url
    return url.get_secret_value() if url else None


@st.cache_data(ttl=300, show_spinner=False)
def _ler(consulta: str, **params: Any) -> list[q.Linha]:
    """Lê a gold, guardando o resultado por 5 minutos."""
    url = _url()
    if url is None:
        msg = "defina DASHBOARD_DATABASE_URL no .env e rode o comando migrate"
        raise LoadError(msg)
    return q.ler(url, consulta, params)


def _estilo(grafico: alt.TopLevelMixin) -> alt.TopLevelMixin:
    return (
        grafico.configure(font=FONTE, background="transparent")
        .configure_axis(
            gridColor=GRADE,
            domainColor=EIXO,
            tickColor=EIXO,
            labelColor=TINTA2,
            titleColor=TINTA2,
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight="normal",
        )
        .configure_legend(
            labelColor=TINTA2, titleColor=TINTA2, orient="bottom", labelFontSize=12
        )
        .configure_view(stroke=None)
    )


def _mostrar(grafico: alt.TopLevelMixin, largura: str = "stretch") -> None:
    st.altair_chart(_estilo(grafico), width=largura, theme=None)


def _milhar() -> str:
    """Expressão do eixo com o ponto separando os milhares, como em ``10.000``."""
    return "replace(format(datum.value, ',.0f'), ',', '.')"


def _com_sinal(valor: float | None) -> str:
    """Escreve um crescimento com sinal: ``+84,0`` ou ``−3,2``."""
    return (
        f"+{numero(valor, 1)}" if valor is not None and valor > 0 else numero(valor, 1)
    )


def _cartao(
    coluna: Any,
    icone: str,
    rotulo: str,
    valor: str,
    detalhe: str,
    destaque: bool = False,
) -> None:
    """Um cartão com símbolo. O cartão do Brasil ganha a borda laranja."""
    prefixo = "cartao_destaque" if destaque else "cartao"
    with coluna, st.container(border=True, key=f"{prefixo}_{rotulo}", height="stretch"):
        st.metric(f":material/{icone}: {rotulo}", valor)
        st.caption(detalhe)


def _painel(nome: str, icone: str, titulo: str, subtitulo: str) -> Any:
    """Abre um painel branco com título que diz a conclusão, e não só o assunto.

    ``height="stretch"`` deixa os painéis lado a lado com a mesma altura, como os
    cartões, qualquer que seja a largura da janela.
    """
    painel = st.container(border=True, key=f"painel_{nome}", height="stretch")
    with painel:
        st.subheader(f":material/{icone}: {titulo}", anchor=False)
        st.caption(subtitulo)
    return painel


def _cores_renda(linhas: list[q.Linha], colunas: int = 2) -> alt.Color:
    ordem = [n for n in CORES_RENDA if any(x["nivel_renda"] == n for x in linhas)]
    return alt.Color(
        "nivel_renda:N",
        scale=alt.Scale(domain=ordem, range=[CORES_RENDA[n] for n in ordem]),
        legend=alt.Legend(title=None, columns=colunas),
        sort=ordem,
    )


# ------------------------------------------------------------------------- Tela 1
def renda_e_vida() -> None:
    """Quem vive em países mais ricos vive mais? E onde o Brasil está?"""
    with st.sidebar:
        anos = [x["ano"] for x in _ler(q.ANOS_PAIS)]
        ano = st.selectbox("Ano", anos, index=anos.index(2023))

    analisados = _ler(q.PAISES_ANALISADOS, ano=ano)[0]
    renda = _ler(q.DIFERENCA_RENDA, ano=ano)[0]
    brasil = _ler(q.BRASIL_NO_ANO, ano=ano)
    vida_brasil = brasil[0]["expectativa_vida"] if brasil else None
    pib_brasil = brasil[0]["pib_per_capita_usd"] if brasil else None
    diferenca = numero(renda["diferenca"], 1)

    st.title("Renda e qualidade de vida", anchor=False)
    c1, c2, c3 = st.columns(3)
    _cartao(
        c1,
        "public",
        "Países analisados",
        f"{analisados['paises_com_valor']} de {analisados['paises_no_grupo']}",
        f"cobertura de {numero(analisados['cobertura_pct'], 0)}%",
    )
    _cartao(
        c2,
        "favorite",
        "Diferença entre renda alta e baixa",
        f"{diferenca} anos",
        f"de expectativa de vida em {ano}",
    )
    _cartao(
        c3,
        "flag",
        "Expectativa de vida no Brasil",
        f"{numero(vida_brasil, 1)} anos",
        f"em {ano}",
        destaque=True,
    )

    esquerda, direita = st.columns([2, 3])
    with (
        esquerda,
        _painel(
            "renda",
            "show_chart",
            f"Renda alta vive {diferenca} anos a mais que renda baixa",
            "Mediana dos países de cada faixa de renda, em anos",
        ),
    ):
        _linhas_renda(_ler(q.EXPECTATIVA_POR_RENDA), renda, ano)
    with (
        direita,
        _painel(
            "dispersao",
            "bubble_chart",
            f"Brasil: US$ {numero(pib_brasil, 0)} por pessoa e "
            f"{numero(vida_brasil, 1)} anos de vida",
            f"Cada bolha é um país em {ano}. Mais à direita = mais rico. Mais acima = "
            "vive mais. Borda vermelha = valor atípico.",
        ),
    ):
        _dispersao(_ler(q.DISPERSAO, ano=ano))


def _linhas_renda(linhas: list[q.Linha], renda: q.Linha, ano: int) -> None:
    com_valor = [x for x in linhas if x["mediana"] is not None]
    for x in com_valor:
        x["valor"] = indicador(x["mediana"], 1)
    ultimo = max(x["ano"] for x in com_valor)
    finais = [x for x in com_valor if x["ano"] == ultimo]
    eixo_x = alt.X(
        "ano:Q",
        title=None,
        axis=alt.Axis(format="d", grid=False, tickCount=5),
        scale=alt.Scale(zero=False, nice=False),
    )
    eixo_y = alt.Y(
        "mediana:Q",
        title=None,
        scale=alt.Scale(zero=False),
        axis=alt.Axis(labelExpr=_milhar(), tickCount=5),
    )
    base = alt.Chart(alt.Data(values=com_valor)).encode(
        x=eixo_x, y=eixo_y, color=_cores_renda(com_valor)
    )
    rotulos = (
        alt.Chart(alt.Data(values=finais))
        .mark_text(align="left", dx=8, fontSize=12, color=TINTA2)
        .encode(x=eixo_x, y=eixo_y, text="valor:N")
    )
    camadas = [
        base.mark_line(strokeWidth=2),
        base.mark_point(filled=True, size=45, opacity=1, stroke="#ffffff").encode(
            tooltip=[
                alt.Tooltip("nivel_renda:N", title="Faixa de renda"),
                alt.Tooltip("ano:O", title="Ano"),
                alt.Tooltip("valor:N", title="Mediana"),
            ]
        ),
        rotulos,
    ]
    if renda["diferenca"] is not None:
        # A distância entre renda alta e baixa, marcada no ano escolhido.
        marca = alt.Data(
            values=[
                {
                    "ano": ano,
                    "baixa": renda["renda_baixa"],
                    "alta": renda["renda_alta"],
                    "meio": (renda["renda_baixa"] + renda["renda_alta"]) / 2,
                    "texto": f"{numero(renda['diferenca'], 1)} anos",
                }
            ]
        )
        x_marca = alt.X("ano:Q")
        camadas.append(
            alt.Chart(marca)
            .mark_rule(color=TINTA, strokeDash=[4, 3], strokeWidth=1.5)
            .encode(x=x_marca, y=alt.Y("baixa:Q"), y2="alta:Q")
        )
        camadas.append(
            alt.Chart(marca)
            .mark_text(align="left", dx=6, fontSize=13, fontWeight=600, color=TINTA)
            .encode(x=x_marca, y=alt.Y("meio:Q"), text="texto:N")
        )
    _mostrar(
        alt.layer(*camadas).properties(
            height=380, padding={"right": 44, "left": 5, "top": 5, "bottom": 5}
        )
    )


def _nomes(
    linhas: list[q.Linha], x: alt.X, y: alt.Y, cor: str, tamanho: int, peso: int
) -> list[alt.Chart]:
    """Nomes de países com um contorno branco, para lerem em cima das bolhas."""
    base = alt.Chart(alt.Data(values=linhas)).encode(x=x, y=y, text="pais:N")
    contorno = base.mark_text(
        fontSize=tamanho,
        fontWeight=peso,
        dy=-22,
        color="#ffffff",
        stroke="#ffffff",
        strokeWidth=4,
    )
    return [
        contorno,
        base.mark_text(fontSize=tamanho, fontWeight=peso, dy=-22, color=cor),
    ]


def _dispersao(linhas: list[q.Linha]) -> None:
    if not linhas:
        st.info("Nenhum país tem os dois valores neste ano.")
        return
    for x in linhas:
        x["pib"] = "US$ " + numero(x["pib_per_capita_usd"], 0)
        x["vida"] = numero(x["expectativa_vida"], 1) + " anos"
        x["pop"] = numero(x["populacao"], 0)
        x["atipico"] = x["motivo_atipico"] or "nenhum"
    outros = [x for x in linhas if not x["destaque"]]
    rotulados = [x for x in outros if x["com_rotulo"]]
    brasil = [x for x in linhas if x["destaque"]]
    eixo_x = alt.X(
        "pib_per_capita_usd:Q",
        title="PIB per capita nominal, em dólares correntes (escala logarítmica)",
        scale=alt.Scale(type="log"),
        axis=alt.Axis(values=[100, 1000, 10000, 100000], labelExpr=_milhar()),
    )
    eixo_y = alt.Y(
        "expectativa_vida:Q",
        title="Expectativa de vida, em anos",
        scale=alt.Scale(zero=False),
    )
    tamanho = alt.Size(
        "populacao:Q",
        # O domínio fixo mantém o tamanho igual entre as bolhas e a do Brasil.
        scale=alt.Scale(
            type="sqrt",
            range=[30, 2200],
            domain=[0, max(x["populacao"] or 0 for x in linhas)],
        ),
        legend=None,
    )
    dicas = [
        alt.Tooltip("pais:N", title="País"),
        alt.Tooltip("nivel_renda:N", title="Faixa de renda"),
        alt.Tooltip("pib:N", title="PIB per capita"),
        alt.Tooltip("vida:N", title="Expectativa de vida"),
        alt.Tooltip("pop:N", title="População"),
        alt.Tooltip("atipico:N", title="Valor atípico"),
    ]
    bolhas = (
        alt.Chart(alt.Data(values=outros))
        .mark_circle(opacity=0.8)
        .encode(
            x=eixo_x,
            y=eixo_y,
            size=tamanho,
            color=_cores_renda(outros, colunas=5),
            stroke=alt.condition(
                "datum.tem_valor_atipico", alt.value(CRITICO), alt.value("#ffffff")
            ),
            strokeWidth=alt.condition(
                "datum.tem_valor_atipico", alt.value(2.5), alt.value(1.5)
            ),
            tooltip=dicas,
        )
    )
    camadas = [bolhas, *_nomes(rotulados, eixo_x, eixo_y, TINTA2, 12, 500)]
    if brasil:
        camadas.append(
            alt.Chart(alt.Data(values=brasil))
            .mark_circle(opacity=1, color=DESTAQUE, stroke=TINTA, strokeWidth=1.5)
            .encode(x=eixo_x, y=eixo_y, size=tamanho, tooltip=dicas)
        )
        camadas.extend(_nomes(brasil, eixo_x, eixo_y, "#c94f1f", 15, 700))
    _mostrar(alt.layer(*camadas).properties(height=420))


# ------------------------------------------------------------------------- Tela 2
def pib_e_crescimento() -> None:
    """Quem são as maiores economias, quem mais cresceu, e onde o Brasil está?"""
    with st.sidebar:
        anos = [x["ano"] for x in _ler(q.ANOS_PAIS)]
        ano = st.selectbox("Ano dos maiores PIBs", anos)
        regioes = [x["regiao"] for x in _ler(q.REGIOES)]
        regiao = st.selectbox("Região", [TODAS, *regioes])
        paises = [x["pais"] for x in _ler(q.PAISES)]
        escolhidos = st.multiselect(
            "Países no gráfico de PIB",
            paises,
            default=[p for p in PAISES_PADRAO if p in paises],
            max_selections=len(CORES_PAISES),
        )
    filtro_regiao = None if regiao == TODAS else regiao

    maior = _ler(q.MAIOR_PIB, ano=ano)
    pib_brasil = _ler(q.BRASIL_PIB, ano=ano)
    cresc_brasil = _ler(q.BRASIL_CRESCIMENTO)
    ranking = _ler(q.RANKING_CRESCIMENTO, regiao=filtro_regiao)
    top = _ler(q.TOP_10_PIB, ano=ano, regiao=filtro_regiao)
    inicio, fim = ranking[0]["ano_inicial"], ranking[0]["ano_final"]
    primeiro = next((x for x in ranking if x["posicao_mundo"] is not None), None)

    st.title("PIB e crescimento", anchor=False)
    c1, c2, c3, c4 = st.columns(4)
    _cartao(
        c1,
        "account_balance",
        "Maior PIB do mundo",
        maior[0]["pais"] if maior else "sem dado",
        f"US$ {numero(maior[0]['pib_bilhoes'], 0)} bilhões em {ano}" if maior else "",
    )
    _cartao(
        c2,
        "flag",
        "Brasil no PIB mundial",
        f"{pib_brasil[0]['posicao']}º" if pib_brasil else "sem dado",
        f"US$ {numero(pib_brasil[0]['pib_bilhoes'], 0)} bilhões em {ano}"
        if pib_brasil
        else "",
        destaque=True,
    )
    _cartao(
        c3,
        "trending_up",
        "Maior crescimento em 10 anos",
        primeiro["pais"] if primeiro else "sem dado",
        f"{_com_sinal(primeiro['crescimento'])}% de {inicio} a {fim}"
        if primeiro
        else "",
    )
    _cartao(
        c4,
        "flag",
        "Brasil no crescimento",
        f"{cresc_brasil[0]['posicao']}º" if cresc_brasil[0]["posicao"] else "sem dado",
        f"{_com_sinal(cresc_brasil[0]['crescimento'])}% de {inicio} a {fim}",
        destaque=True,
    )

    esquerda, direita = st.columns([3, 2])
    with (
        esquerda,
        _painel(
            "pib",
            "show_chart",
            "Como o PIB evoluiu desde 2000",
            "PIB nominal, em US$ bilhões. Escolha os países na barra lateral.",
        ),
    ):
        _linhas_pib(_ler(q.PIB_POR_PAIS, paises=escolhidos), escolhidos)
    with (
        direita,
        _painel(
            "top",
            "emoji_events",
            f"{top[0]['pais']} lidera os maiores PIBs" if top else "Os maiores PIBs",
            f"Em {ano}, em US$ bilhões. O Brasil é o {pib_brasil[0]['posicao']}º."
            if pib_brasil
            else f"Os 10 maiores em {ano}, em US$ bilhões",
        ),
    ):
        _top_10(top)

    with (
        _painel(
            "ranking",
            "leaderboard",
            f"{primeiro['pais']} lidera o crescimento de {inicio} a {fim}"
            if primeiro
            else f"Crescimento de {inicio} a {fim}",
            "Crescimento real do PIB, sem a inflação. O Brasil é o "
            f"{cresc_brasil[0]['posicao']}º. Role para ver todos os países.",
        ),
        st.container(height=500, border=False),
    ):
        _tabela_ranking(ranking)


def _linhas_pib(linhas: list[q.Linha], escolhidos: list[str]) -> None:
    if not linhas:
        st.info("Escolha pelo menos um país na barra lateral.")
        return
    for x in linhas:
        x["valor"] = numero(x["pib_bilhoes"], 0)
    finais = {x["pais"]: x for x in linhas}
    outras = iter(CORES_PAISES)
    cores = [DESTAQUE if p == BRASIL else next(outras) for p in escolhidos]
    cor = alt.Color(
        "pais:N",
        scale=alt.Scale(domain=escolhidos, range=cores),
        legend=alt.Legend(title=None),
    )
    eixo_x = alt.X(
        "ano:Q",
        title=None,
        axis=alt.Axis(format="d", grid=False, tickCount=5),
        scale=alt.Scale(zero=False, nice=False),
    )
    eixo_y = alt.Y(
        "pib_bilhoes:Q", title=None, axis=alt.Axis(labelExpr=_milhar(), tickCount=5)
    )
    base = alt.Chart(alt.Data(values=linhas)).encode(x=eixo_x, y=eixo_y, color=cor)
    rotulos = (
        alt.Chart(alt.Data(values=list(finais.values())))
        .mark_text(align="left", dx=8, fontSize=12, color=TINTA2)
        .encode(x=eixo_x, y=eixo_y, text="valor:N")
    )
    _mostrar(
        alt.layer(
            base.mark_line(strokeWidth=2.5),
            base.mark_point(filled=True, size=35, opacity=1, stroke="#ffffff").encode(
                tooltip=[
                    alt.Tooltip("pais:N", title="País"),
                    alt.Tooltip("ano:O", title="Ano"),
                    alt.Tooltip("valor:N", title="PIB, em US$ bilhões"),
                ]
            ),
            rotulos,
        ).properties(
            height=340, padding={"right": 56, "left": 5, "top": 5, "bottom": 5}
        )
    )


def _top_10(linhas: list[q.Linha]) -> None:
    if not linhas:
        st.info("Não há PIB para este filtro.")
        return
    for x in linhas:
        x["valor"] = numero(x["pib_bilhoes"], 0)
        x["cor"] = DESTAQUE if x["destaque"] else CONTEXTO
    y = alt.Y(
        "pais:N",
        sort=[x["pais"] for x in linhas],
        title=None,
        axis=alt.Axis(ticks=False, domain=False, labelLimit=150, labelColor=TINTA),
    )
    x_barra = alt.X("pib_bilhoes:Q", axis=None, scale=alt.Scale(nice=False))
    base = alt.Chart(alt.Data(values=linhas)).encode(y=y, x=x_barra)
    _mostrar(
        alt.layer(
            base.mark_bar(cornerRadiusEnd=4).encode(
                color=alt.Color("cor:N", scale=None),
                tooltip=[
                    alt.Tooltip("pais:N", title="País"),
                    alt.Tooltip("valor:N", title="PIB, em US$ bilhões"),
                ],
            ),
            base.mark_text(align="left", dx=5, fontSize=12, color=TINTA).encode(
                text="valor:N"
            ),
        ).properties(
            height=340, padding={"right": 56, "left": 5, "top": 5, "bottom": 5}
        )
    )


def _tabela_ranking(linhas: list[q.Linha]) -> None:
    """Tabela com barras: um só gráfico, com cada coluna em uma posição fixa."""
    for x in linhas:
        x["pos_m"] = f"{x['posicao_mundo']}º" if x["posicao_mundo"] else "—"
        x["pos_r"] = f"{x['posicao_regiao']}º" if x["posicao_regiao"] else "—"
        x["cresc_txt"] = numero(x["crescimento"], 1)
        x["cresc_x"] = x["crescimento"] or 0
        queda = (x["crescimento"] or 0) < 0
        x["cor"] = DESTAQUE if x["destaque"] else QUEDA if queda else CONTEXTO
        x["cor_texto"] = DESTAQUE if x["destaque"] else TINTA
    dados = alt.Data(values=linhas)
    y = alt.Y(
        "pais:N",
        sort=[x["pais"] for x in linhas],
        axis=None,
        scale=alt.Scale(type="band", paddingInner=0.25),
    )
    cor_texto = alt.Color("cor_texto:N", scale=None)
    colunas = [
        ("pos_m", "Pos. mundo", 0, 70, 600),
        ("pais", "País", 70, 160, 400),
        ("regiao", "Região", 236, 205, 400),
        ("nivel_renda_atual", "Faixa de renda atual", 447, 130, 400),
        ("pos_r", "Pos. região", 845, 60, 400),
    ]
    camadas = [
        alt.Chart(dados)
        .mark_text(align="left", fontSize=13, limit=largura, fontWeight=peso)
        .encode(y=y, x=alt.value(inicio), text=f"{campo}:N", color=cor_texto)
        for campo, _, inicio, largura, peso in colunas
    ]
    cabecalho = [
        {"titulo": titulo, "x": inicio} for _, titulo, inicio, _, _ in colunas
    ] + [{"titulo": "Crescimento, em %", "x": 585}]
    camadas.append(
        alt.Chart(alt.Data(values=cabecalho))
        .mark_text(align="left", fontSize=12, fontWeight=600, color=TINTA2)
        .encode(x=alt.X("x:Q", scale=None), y=alt.value(-14), text="titulo:N")
    )
    # As barras ficam entre 585 e 790 pixels, com a linha de base no zero.
    x = alt.X("cresc_x:Q", axis=None, scale=alt.Scale(range=[585, 790], nice=False))
    camadas.append(
        alt.Chart(dados)
        .transform_filter("datum.crescimento !== null")
        .mark_bar()
        .encode(
            x=x,
            x2=alt.datum(0),
            y=y,
            color=alt.Color("cor:N", scale=None),
            tooltip=[
                alt.Tooltip("pais:N", title="País"),
                alt.Tooltip("regiao:N", title="Região"),
                alt.Tooltip("cresc_txt:N", title="Crescimento, em %"),
            ],
        )
    )
    camadas.append(
        alt.Chart(dados)
        .mark_text(align="left", dx=5, fontSize=13)
        .encode(x=x, y=y, text="cresc_txt:N", color=cor_texto)
    )
    _mostrar(
        alt.layer(*camadas).properties(
            width=905, height=30 * len(linhas), padding={"top": 26}
        ),
        largura="content",
    )
