-- gold.ranking_crescimento
-- Pergunta de negócio: Quais países mais cresceram na última década, em PIB real e em população urbana, por região?
-- Grão (o que é uma linha): um país, na janela dos últimos 10 anos com dado.
-- Origem: silver.fato_observacao, silver.dim_pais, silver.dim_regiao, silver.dim_nivel_renda, silver.valor_atipico
-- Regras: só países, sem agregados (D-023). PIB real, com as taxas anuais compostas, e exige os 10 anos (D-064). População urbana = população x percentual urbano (D-065). Salto de população dentro da janela tira o país do ranking urbano (D-062). País sem dado fica na view, sem posição (D-042, D-064).
-- Chave: pais_iso3
-- Coluna pais_iso3: Código ISO3 do país.
-- Coluna pais: Nome do país.
-- Coluna regiao_id: Código da região geográfica atual.
-- Coluna regiao: Nome da região.
-- Coluna nivel_renda_atual_id: Nível de renda atual; não é o de cada ano da janela (D-025).
-- Coluna nivel_renda_atual: Nome do nível de renda atual.
-- Coluna ano_inicial: Ano-base da janela: 10 anos antes de ano_final.
-- Coluna ano_final: Último ano com crescimento do PIB no fato (D-064).
-- Coluna crescimento_pib_real_pct: Crescimento real do PIB na janela, em %; NULL se faltar um ano (D-064).
-- Coluna posicao_pib_regiao: Posição na região, do maior para o menor crescimento; NULL sem crescimento.
-- Coluna posicao_pib_mundo: Posição no mundo, do maior para o menor crescimento; NULL sem crescimento.
-- Coluna populacao_urbana_inicial: População urbana em ano_inicial (D-065).
-- Coluna populacao_urbana_final: População urbana em ano_final (D-065).
-- Coluna crescimento_populacao_urbana_pct: Variação da população urbana na janela, em %; NULL se houver salto de população (D-062).
-- Coluna posicao_populacao_urbana_regiao: Posição na região; NULL sem crescimento.
-- Coluna posicao_populacao_urbana_mundo: Posição no mundo; NULL sem crescimento.
-- Coluna motivo_remocao: Por que o país ficou sem crescimento urbano; NULL se ficou com ele (D-062).
with janela as (
    select max(f.ano) - 10 as ano_inicial, max(f.ano) as ano_final
    from silver.fato_observacao as f
    join silver.dim_pais as p on p.pais_iso3 = f.pais_iso3 and not p.e_agregado
    where f.indicador_id = 'NY.GDP.MKTP.KD.ZG' and f.valor is not null
),
pib as (
    select
        f.pais_iso3,
        count(f.valor) as anos_com_valor,
        exp(sum(ln(1 + f.valor / 100))) as fator
    from silver.fato_observacao as f
    cross join janela as j
    where f.indicador_id = 'NY.GDP.MKTP.KD.ZG'
      and f.ano > j.ano_inicial
      and f.ano <= j.ano_final
    group by f.pais_iso3
),
urbana as (
    select
        pop.pais_iso3,
        max(pop.valor * urb.valor / 100) filter (where pop.ano = j.ano_inicial) as inicial,
        max(pop.valor * urb.valor / 100) filter (where pop.ano = j.ano_final) as final
    from silver.fato_observacao as pop
    join silver.fato_observacao as urb
        on urb.pais_iso3 = pop.pais_iso3
        and urb.ano = pop.ano
        and urb.indicador_id = 'SP.URB.TOTL.IN.ZS'
    cross join janela as j
    where pop.indicador_id = 'SP.POP.TOTL'
      and pop.ano in (j.ano_inicial, j.ano_final)
    group by pop.pais_iso3
),
salto as (
    select a.pais_iso3, string_agg(a.motivo || ' (' || a.ano || ')', '; ' order by a.ano) as motivo
    from silver.valor_atipico as a
    cross join janela as j
    where a.indicador_id = 'SP.POP.TOTL'
      and a.ano > j.ano_inicial
      and a.ano <= j.ano_final
    group by a.pais_iso3
),
calculo as (
    select
        p.pais_iso3,
        p.nome as pais,
        p.regiao_id,
        r.nome as regiao,
        p.nivel_renda_atual_id,
        n.nome as nivel_renda_atual,
        j.ano_inicial,
        j.ano_final,
        case when pib.anos_com_valor = j.ano_final - j.ano_inicial then 100 * (pib.fator - 1) end
            as crescimento_pib_real_pct,
        u.inicial as populacao_urbana_inicial,
        u.final as populacao_urbana_final,
        case when s.motivo is null and u.inicial > 0 then 100 * (u.final / u.inicial - 1) end
            as crescimento_populacao_urbana_pct,
        s.motivo as motivo_remocao
    from silver.dim_pais as p
    cross join janela as j
    join silver.dim_regiao as r on r.regiao_id = p.regiao_id
    join silver.dim_nivel_renda as n on n.nivel_renda_id = p.nivel_renda_atual_id
    left join pib on pib.pais_iso3 = p.pais_iso3
    left join urbana as u on u.pais_iso3 = p.pais_iso3
    left join salto as s on s.pais_iso3 = p.pais_iso3
    where not p.e_agregado
)
select
    pais_iso3,
    pais,
    regiao_id,
    regiao,
    nivel_renda_atual_id,
    nivel_renda_atual,
    ano_inicial,
    ano_final,
    crescimento_pib_real_pct,
    case when crescimento_pib_real_pct is not null then
        rank() over (
            partition by regiao_id, crescimento_pib_real_pct is null
            order by crescimento_pib_real_pct desc
        )
    end as posicao_pib_regiao,
    case when crescimento_pib_real_pct is not null then
        rank() over (
            partition by crescimento_pib_real_pct is null
            order by crescimento_pib_real_pct desc
        )
    end as posicao_pib_mundo,
    populacao_urbana_inicial,
    populacao_urbana_final,
    crescimento_populacao_urbana_pct,
    case when crescimento_populacao_urbana_pct is not null then
        rank() over (
            partition by regiao_id, crescimento_populacao_urbana_pct is null
            order by crescimento_populacao_urbana_pct desc
        )
    end as posicao_populacao_urbana_regiao,
    case when crescimento_populacao_urbana_pct is not null then
        rank() over (
            partition by crescimento_populacao_urbana_pct is null
            order by crescimento_populacao_urbana_pct desc
        )
    end as posicao_populacao_urbana_mundo,
    motivo_remocao
from calculo;
