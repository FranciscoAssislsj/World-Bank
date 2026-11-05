"""Dashboard Streamlit do projeto: lê só a gold, com o usuário só de leitura.

Rodar: ``uv run --group dashboard streamlit run dashboard/app.py``
"""

import paginas
import streamlit as st

st.set_page_config(
    page_title="Banco Mundial: indicadores",
    page_icon=":material/public:",
    layout="wide",
)

# O que o tema não alcança: tamanhos, cartões brancos e o destaque do Brasil.
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.65rem !important; font-weight: 700 !important; }
    h3 { font-size: 1.05rem !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; }
    [data-testid="stMetricLabel"] p { font-size: 0.85rem; }
    [class*="st-key-cartao"], [class*="st-key-painel"] {
        background: #ffffff;
        border-color: #e6e8eb !important;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(13, 54, 107, 0.08);
    }
    [class*="st-key-cartao_destaque"] { border-left: 4px solid #eb6834 !important; }
    [class*="st-key-cartao_destaque"] [data-testid="stMetricValue"] { color: #c94f1f; }
    [class*="st-key-cartao_destaque"] [data-testid="stMetricLabel"] span {
        color: #c94f1f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

PAGINAS = [
    st.Page(
        paginas.renda_e_vida,
        title="Renda e qualidade de vida",
        icon=":material/favorite:",
        url_path="renda",
        default=True,
    ),
    st.Page(
        paginas.pib_e_crescimento,
        title="PIB e crescimento",
        icon=":material/payments:",
        url_path="pib",
    ),
]

# O menu automático ficaria acima do título. Escondido, os links seguem o layout.
atual = st.navigation(PAGINAS, position="hidden")
# O link da página inicial tem o endereço vazio, e o link ativo não tem marca própria.
endereco = "" if atual is PAGINAS[0] else atual.url_path
st.markdown(
    f"""<style>[data-testid="stPageLink-NavLink"][href="{endereco}"] {{
    background-color: rgba(255, 255, 255, 0.18) !important; }}</style>""",
    unsafe_allow_html=True,
)
with st.sidebar:
    st.markdown("### :material/public: Banco Mundial")
    st.caption("Indicadores, 2000 a 2024")
    for pagina in PAGINAS:
        st.page_link(pagina)
    st.divider()
    st.caption(":material/tune: FILTROS")
atual.run()
