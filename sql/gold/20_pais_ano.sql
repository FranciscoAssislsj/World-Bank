-- gold.pais_ano
-- Pergunta de negócio: Como PIB per capita, expectativa de vida, eletricidade e internet se relacionam em cada país e ano?
-- Grão (o que é uma linha): um país em um ano, com um indicador por coluna.
-- Origem: gold.fato_observacao, gold.dim_pais, gold.valores_atipicos, gold.dim_regiao, gold.fato_renda_anual, gold.dim_nivel_renda
-- Regras: Nomes em português, vindos das dimensões (D-082). só países, sem agregados (D-023). A renda é a daquele ano (D-038, D-059). Valor ausente fica NULL, sem preencher (D-042, D-063). Todo valor é o da fonte, e o atípico só ganha uma marca (D-062, D-070).
-- Chave: pais_iso3, ano
-- Coluna pais_iso3: Código ISO3 do país.
-- Coluna pais: Nome do país.
-- Coluna ano: Ano da observação.
-- Coluna regiao_id: Código da região geográfica atual; a fonte não tem histórico.
-- Coluna regiao: Nome da região.
-- Coluna nivel_renda_id: Nível de renda naquele ano; NULL se o país não foi classificado (D-059).
-- Coluna nivel_renda: Nome do nível de renda naquele ano.
-- Coluna nivel_renda_ordem: Ordem do nível, do menor para o maior, para ordenar gráficos.
-- Coluna populacao: População total (SP.POP.TOTL).
-- Coluna populacao_urbana_pct: População urbana, em % do total (SP.URB.TOTL.IN.ZS).
-- Coluna expectativa_vida: Expectativa de vida ao nascer, em anos (SP.DYN.LE00.IN).
-- Coluna pib_usd: PIB em dólares correntes (NY.GDP.MKTP.CD).
-- Coluna pib_per_capita_usd: PIB per capita em dólares correntes (NY.GDP.PCAP.CD).
-- Coluna crescimento_pib_pct: Crescimento real do PIB no ano, em % (NY.GDP.MKTP.KD.ZG).
-- Coluna inflacao_pct: Inflação ao consumidor no ano, em % (FP.CPI.TOTL.ZG).
-- Coluna desemprego_pct: Desemprego, em % da força de trabalho (SL.UEM.TOTL.ZS).
-- Coluna pobreza_pct: População abaixo da linha de US$ 3,00 por dia, em % (SI.POV.DDAY).
-- Coluna gini: Índice de Gini (SI.POV.GINI).
-- Coluna alfabetizacao_pct: Alfabetização de adultos, em % (SE.ADT.LITR.ZS).
-- Coluna gasto_saude_pib_pct: Gasto corrente em saúde, em % do PIB (SH.XPD.CHEX.GD.ZS).
-- Coluna acesso_eletricidade_pct: Acesso à eletricidade, em % da população (EG.ELC.ACCS.ZS).
-- Coluna acesso_internet_pct: Pessoas que usam internet, em % da população (IT.NET.USER.ZS).
-- Coluna co2_per_capita: CO2 por pessoa, em toneladas de CO2 equivalente (EN.GHG.CO2.PC.CE.AR5).
-- Coluna tem_valor_atipico: true quando algum valor desta linha foi apontado como estranho; o motivo diz qual (D-062).
-- Coluna motivo_atipico: Qual valor foi apontado e por quê; NULL se nenhum foi (D-062).
-- Coluna grupo_grafico: Cor do país nos gráficos: Brasil, Valor atípico ou a faixa de renda do ano (D-084, D-085).
-- Coluna grupo_grafico_ordem: Ordem do grupo na legenda: da menor renda à maior, com o Brasil por último (D-084, D-085).
-- Coluna nivel_renda_rotulo: Nível de renda para a legenda; Não classificado quando não há (D-097).
-- Coluna e_brasil: true na linha do Brasil, para o destaque dos dashboards (D-084, D-097).
-- Coluna pib_bilhoes_usd: PIB em bilhões de dólares correntes, a unidade dos gráficos (D-097).
-- Coluna posicao_pib_mundo: Posição do PIB entre os países no ano, do maior para o menor; NULL sem PIB (D-097).
-- Coluna posicao_pib_regiao: Posição do PIB entre os países da região no ano; NULL sem PIB (D-097).
-- Coluna rotulo_dispersao: true nos 6 países mais populosos do ano com PIB per capita e expectativa de vida, os que ganham nome no gráfico (D-097).
with base as (
    select
        f.pais_iso3,
        f.ano,
        f.indicador_id,
        f.valor,
        a.motivo
    from gold.fato_observacao as f
    join gold.dim_pais as p on p.pais_iso3 = f.pais_iso3 and not p.e_agregado
    left join gold.valores_atipicos as a
        on a.pais_iso3 = f.pais_iso3
        and a.indicador_id = f.indicador_id
        and a.ano = f.ano
),
linha as (
    select
        p.pais_iso3,
        p.nome as pais,
        b.ano,
        p.regiao_id,
        r.nome as regiao,
        c.nivel_renda_id,
        n.nome as nivel_renda,
        n.ordem as nivel_renda_ordem,
        max(b.valor) filter (where b.indicador_id = 'SP.POP.TOTL') as populacao,
        max(b.valor) filter (where b.indicador_id = 'SP.URB.TOTL.IN.ZS') as populacao_urbana_pct,
        max(b.valor) filter (where b.indicador_id = 'SP.DYN.LE00.IN') as expectativa_vida,
        max(b.valor) filter (where b.indicador_id = 'NY.GDP.MKTP.CD') as pib_usd,
        max(b.valor) filter (where b.indicador_id = 'NY.GDP.PCAP.CD') as pib_per_capita_usd,
        max(b.valor) filter (where b.indicador_id = 'NY.GDP.MKTP.KD.ZG') as crescimento_pib_pct,
        max(b.valor) filter (where b.indicador_id = 'FP.CPI.TOTL.ZG') as inflacao_pct,
        max(b.valor) filter (where b.indicador_id = 'SL.UEM.TOTL.ZS') as desemprego_pct,
        max(b.valor) filter (where b.indicador_id = 'SI.POV.DDAY') as pobreza_pct,
        max(b.valor) filter (where b.indicador_id = 'SI.POV.GINI') as gini,
        max(b.valor) filter (where b.indicador_id = 'SE.ADT.LITR.ZS') as alfabetizacao_pct,
        max(b.valor) filter (where b.indicador_id = 'SH.XPD.CHEX.GD.ZS') as gasto_saude_pib_pct,
        max(b.valor) filter (where b.indicador_id = 'EG.ELC.ACCS.ZS') as acesso_eletricidade_pct,
        max(b.valor) filter (where b.indicador_id = 'IT.NET.USER.ZS') as acesso_internet_pct,
        max(b.valor) filter (where b.indicador_id = 'EN.GHG.CO2.PC.CE.AR5') as co2_per_capita,
        count(b.motivo) > 0 as tem_valor_atipico,
        string_agg(b.motivo, '; ' order by b.motivo) as motivo_atipico,
        case
            when p.pais_iso3 = 'BRA' then 'Brasil'
            when count(b.motivo) > 0 then 'Valor atípico'
            else coalesce(n.nome, 'Não classificado')
        end as grupo_grafico,
        case
            when p.pais_iso3 = 'BRA' then 7
            when count(b.motivo) > 0 then 6
            else coalesce(n.ordem + 1, 1)
        end as grupo_grafico_ordem
    from base as b
    join gold.dim_pais as p on p.pais_iso3 = b.pais_iso3
    join gold.dim_regiao as r on r.regiao_id = p.regiao_id
    left join gold.fato_renda_anual as c
        on c.pais_iso3 = b.pais_iso3 and c.ano_referencia = b.ano
    left join gold.dim_nivel_renda as n on n.nivel_renda_id = c.nivel_renda_id
    group by
        p.pais_iso3, p.nome, b.ano, p.regiao_id, r.nome,
        c.nivel_renda_id, n.nome, n.ordem
)
select
    l.pais_iso3,
    l.pais,
    l.ano,
    l.regiao_id,
    l.regiao,
    l.nivel_renda_id,
    l.nivel_renda,
    l.nivel_renda_ordem,
    l.populacao,
    l.populacao_urbana_pct,
    l.expectativa_vida,
    l.pib_usd,
    l.pib_per_capita_usd,
    l.crescimento_pib_pct,
    l.inflacao_pct,
    l.desemprego_pct,
    l.pobreza_pct,
    l.gini,
    l.alfabetizacao_pct,
    l.gasto_saude_pib_pct,
    l.acesso_eletricidade_pct,
    l.acesso_internet_pct,
    l.co2_per_capita,
    l.tem_valor_atipico,
    l.motivo_atipico,
    l.grupo_grafico,
    l.grupo_grafico_ordem,
    coalesce(l.nivel_renda, 'Não classificado') as nivel_renda_rotulo,
    l.pais_iso3 = 'BRA' as e_brasil,
    l.pib_usd / 1e9 as pib_bilhoes_usd,
    case when l.pib_usd is not null then
        rank() over (partition by l.ano, l.pib_usd is null order by l.pib_usd desc)
    end as posicao_pib_mundo,
    case when l.pib_usd is not null then
        rank() over (partition by l.ano, l.regiao_id, l.pib_usd is null order by l.pib_usd desc)
    end as posicao_pib_regiao,
    coalesce(
        l.pib_per_capita_usd is not null
        and l.expectativa_vida is not null
        and row_number() over (
            partition by l.ano, l.pib_per_capita_usd is not null and l.expectativa_vida is not null
            order by l.populacao desc nulls last, l.pais
        ) <= 6,
        false
    ) as rotulo_dispersao
from linha as l;
