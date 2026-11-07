-- gold.resumo_anual
-- Pergunta de negócio: Em cada ano, quantos países têm dado, quanto a renda muda a expectativa de vida, quem tem o maior PIB e onde o Brasil está?
-- Grão (o que é uma linha): um ano.
-- Origem: gold.fato_observacao, gold.dim_pais, gold.fato_renda_anual
-- Regras: Números dos cartões dos dashboards, calculados aqui para o Streamlit e o Power BI mostrarem o mesmo valor (D-078, D-085). Lê a estrela da gold (D-087). Só países, sem agregados (D-023). A renda é a daquele ano (D-038, D-059). A mediana é a mesma de gold.resumo_renda_regiao (D-061). A posição no PIB vem do PIB nominal do ano. Ano sem dado fica NULL, sem preencher (D-042, D-063). O Brasil é a referência das telas (D-084).
-- Chave: ano
-- Coluna ano: Ano da observação; serve de filtro de ano no Power BI.
-- Coluna paises_com_valor: Países com expectativa de vida neste ano.
-- Coluna paises_no_grupo: Total de países neste ano.
-- Coluna cobertura_pct: paises_com_valor em % de paises_no_grupo.
-- Coluna mediana_renda_alta: Mediana da expectativa de vida dos países de renda alta, em anos.
-- Coluna mediana_renda_baixa: Mediana da expectativa de vida dos países de renda baixa, em anos.
-- Coluna diferenca_renda_anos: Renda alta menos renda baixa, em anos; NULL se faltar uma delas.
-- Coluna maior_pib_pais: País com o maior PIB nominal do ano.
-- Coluna maior_pib_bilhoes: PIB nominal desse país, em US$ bilhões.
-- Coluna brasil_expectativa_vida: Expectativa de vida no Brasil, em anos.
-- Coluna brasil_pib_per_capita_usd: PIB per capita nominal do Brasil, em dólares correntes.
-- Coluna brasil_pib_bilhoes: PIB nominal do Brasil, em US$ bilhões.
-- Coluna brasil_posicao_pib: Posição do Brasil no PIB nominal mundial do ano.
with observacao as (
    select
        f.ano,
        f.pais_iso3,
        p.nome as pais,
        f.indicador_id,
        f.valor,
        c.nivel_renda_id
    from gold.fato_observacao as f
    join gold.dim_pais as p on p.pais_iso3 = f.pais_iso3 and not p.e_agregado
    left join gold.fato_renda_anual as c
        on c.pais_iso3 = f.pais_iso3 and c.ano_referencia = f.ano
    where f.indicador_id in ('SP.DYN.LE00.IN', 'NY.GDP.MKTP.CD', 'NY.GDP.PCAP.CD')
),
vida as (
    select
        ano,
        count(valor) as paises_com_valor,
        count(*) as paises_no_grupo,
        round(100.0 * count(valor) / count(*), 1) as cobertura_pct,
        (percentile_cont(0.5) within group (order by valor::double precision)
            filter (where nivel_renda_id = 'HIC'))::numeric as mediana_renda_alta,
        (percentile_cont(0.5) within group (order by valor::double precision)
            filter (where nivel_renda_id = 'LIC'))::numeric as mediana_renda_baixa
    from observacao
    where indicador_id = 'SP.DYN.LE00.IN'
    group by ano
),
pib as (
    select
        ano,
        pais_iso3,
        pais,
        valor / 1e9 as bilhoes,
        rank() over (partition by ano order by valor desc) as posicao,
        row_number() over (partition by ano order by valor desc, pais) as ordem
    from observacao
    where indicador_id = 'NY.GDP.MKTP.CD' and valor is not null
)
select
    v.ano,
    v.paises_com_valor,
    v.paises_no_grupo,
    v.cobertura_pct,
    v.mediana_renda_alta,
    v.mediana_renda_baixa,
    v.mediana_renda_alta - v.mediana_renda_baixa as diferenca_renda_anos,
    maior.pais as maior_pib_pais,
    maior.bilhoes as maior_pib_bilhoes,
    vida_br.valor as brasil_expectativa_vida,
    per_capita_br.valor as brasil_pib_per_capita_usd,
    pib_br.bilhoes as brasil_pib_bilhoes,
    pib_br.posicao as brasil_posicao_pib
from vida as v
left join pib as maior on maior.ano = v.ano and maior.ordem = 1
left join pib as pib_br on pib_br.ano = v.ano and pib_br.pais_iso3 = 'BRA'
left join observacao as vida_br
    on vida_br.ano = v.ano and vida_br.pais_iso3 = 'BRA'
    and vida_br.indicador_id = 'SP.DYN.LE00.IN'
left join observacao as per_capita_br
    on per_capita_br.ano = v.ano and per_capita_br.pais_iso3 = 'BRA'
    and per_capita_br.indicador_id = 'NY.GDP.PCAP.CD';
