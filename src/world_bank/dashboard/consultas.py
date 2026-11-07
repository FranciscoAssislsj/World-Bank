"""As consultas dos dashboards: todo número da tela sai daqui, e só da gold (D-078).

Os filtros entram sempre como parâmetros, nunca colados no texto do SQL. O teste
``tests/dashboard/test_consultas.py`` recusa qualquer ``FROM`` ou ``JOIN`` fora de
``gold.``, e o usuário ``dashboard_leitor`` nem conseguiria ler outra camada (D-079).
"""

from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row

from world_bank.exceptions import LoadError

Linha = dict[str, Any]

_FILTRO_REGIAO = "(%(regiao)s::text is null or regiao = %(regiao)s)"

ANOS_PAIS = "select distinct ano from gold.pais_ano order by ano desc"

# --- Tela 1: renda e qualidade de vida ---------------------------------------------
PAISES_ANALISADOS = """
select paises_com_valor, paises_no_grupo, cobertura_pct
from gold.resumo_anual
where ano = %(ano)s
"""
EXPECTATIVA_POR_RENDA = """
select ano, nivel_renda, nivel_renda_ordem, mediana
from gold.resumo_renda_regiao
where recorte = 'renda' and indicador_id = 'SP.DYN.LE00.IN'
order by nivel_renda_ordem, ano
"""
DISPERSAO = """
select pais, pais_iso3 = 'BRA' as destaque,
       coalesce(nivel_renda, 'Não classificado') as nivel_renda,
       pib_per_capita_usd, expectativa_vida, populacao,
       tem_valor_atipico, motivo_atipico,
       row_number() over (order by populacao desc nulls last) <= 6 as com_rotulo
from gold.pais_ano
where ano = %(ano)s
  and pib_per_capita_usd is not null and expectativa_vida is not null
order by populacao desc nulls last
"""

DIFERENCA_RENDA = """
select mediana_renda_alta as renda_alta, mediana_renda_baixa as renda_baixa,
       diferenca_renda_anos as diferenca
from gold.resumo_anual
where ano = %(ano)s
"""
BRASIL_NO_ANO = """
select brasil_expectativa_vida as expectativa_vida,
       brasil_pib_per_capita_usd as pib_per_capita_usd
from gold.resumo_anual
where ano = %(ano)s
"""

# --- Tela 2: PIB e crescimento -----------------------------------------------------
REGIOES = "select distinct regiao from gold.ranking_crescimento order by regiao"
PAISES = "select distinct pais from gold.pais_ano order by pais"
PIB_POR_PAIS = """
select ano, pais, pib_usd / 1e9 as pib_bilhoes
from gold.pais_ano
where pais = any(%(paises)s) and pib_usd is not null
order by pais, ano
"""
TOP_10_PIB = f"""
select pais, pais_iso3 = 'BRA' as destaque, pib_usd / 1e9 as pib_bilhoes
from gold.pais_ano
where ano = %(ano)s and pib_usd is not null and {_FILTRO_REGIAO}
order by pib_usd desc
limit 10
"""
RANKING_CRESCIMENTO = f"""
select pais, pais_iso3 = 'BRA' as destaque, regiao, nivel_renda_atual,
       ano_inicial, ano_final,
       crescimento_pib_real_pct as crescimento,
       posicao_pib_mundo as posicao_mundo, posicao_pib_regiao as posicao_regiao
from gold.ranking_crescimento
where {_FILTRO_REGIAO}
order by posicao_pib_mundo nulls last, pais
"""
BRASIL_PIB = """
select brasil_posicao_pib as posicao, brasil_pib_bilhoes as pib_bilhoes
from gold.resumo_anual
where ano = %(ano)s and brasil_posicao_pib is not null
"""
MAIOR_PIB = """
select maior_pib_pais as pais, maior_pib_bilhoes as pib_bilhoes
from gold.resumo_anual
where ano = %(ano)s and maior_pib_pais is not null
"""
BRASIL_CRESCIMENTO = """
select crescimento_pib_real_pct as crescimento, posicao_pib_mundo as posicao
from gold.ranking_crescimento
where pais_iso3 = 'BRA'
"""


def _para_tela(valor: Any) -> Any:
    """Troca ``Decimal`` por ``float``, o tipo que os gráficos entendem."""
    return float(valor) if isinstance(valor, Decimal) else valor


def ler(url: str, consulta: str, params: dict[str, Any] | None = None) -> list[Linha]:
    """Roda uma consulta só de leitura e devolve as linhas.

    Args:
        url: ``DASHBOARD_DATABASE_URL``.
        consulta: Uma das consultas deste módulo.
        params: Os filtros escolhidos na tela.

    Returns:
        Uma lista com um dicionário por linha.

    Raises:
        LoadError: Se o banco estiver desligado ou a consulta falhar.
    """
    try:
        with psycopg.connect(url, row_factory=dict_row) as conn:
            linhas = conn.execute(consulta, params or {}).fetchall()
    except psycopg.Error as exc:
        raise LoadError(f"não foi possível ler a gold: {exc}") from exc
    return [{k: _para_tela(v) for k, v in linha.items()} for linha in linhas]
