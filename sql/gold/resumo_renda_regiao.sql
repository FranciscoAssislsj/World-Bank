-- gold.resumo_renda_regiao
-- Pergunta de negócio: Como cada indicador evolui por nível de renda e por região, incluindo pobreza e desigualdade?
-- Grão (o que é uma linha): um indicador em um ano, em um recorte (renda_regiao, renda, regiao ou mundo).
-- Origem: silver.fato_observacao, silver.dim_pais, silver.dim_regiao, silver.dim_nivel_renda, silver.dim_indicador, silver.classificacao_renda_anual, silver.valor_atipico
-- Regras: só países, sem agregados (D-023). A renda é a daquele ano, e país sem classificação sai só dos recortes de renda (D-059). Os recortes vêm prontos porque mediana não se soma; filtre por recorte para não contar em dobro (D-060). Média simples e mediana, sem ponderar (D-061). A média e a mediana usam todos os valores da fonte, e media_sem_atipicos deixa de fora os que distorcem o grupo (D-062, D-070). A contagem de países mostra a cobertura (D-063).
-- Chave: recorte, ano, indicador_id, nivel_renda_id, regiao_id
-- Coluna recorte: renda_regiao, renda, regiao ou mundo (D-060).
-- Coluna ano: Ano da observação.
-- Coluna indicador_id: Código do indicador.
-- Coluna indicador: Nome do indicador, como vem da API.
-- Coluna nivel_renda_id: Nível de renda naquele ano; NULL se o recorte não usa renda.
-- Coluna nivel_renda: Nome do nível de renda.
-- Coluna nivel_renda_ordem: Ordem do nível, do menor para o maior, para ordenar gráficos.
-- Coluna regiao_id: Código da região; NULL se o recorte não usa região.
-- Coluna regiao: Nome da região.
-- Coluna media: Média simples com todos os valores da fonte; cada país pesa igual (D-061).
-- Coluna media_sem_atipicos: Média simples sem os valores que distorcem o grupo; é a recomendada para análise (D-062).
-- Coluna mediana: Mediana com todos os valores da fonte; quase não muda com um valor extremo (D-061).
-- Coluna paises_com_valor: Quantos países têm valor (D-063).
-- Coluna paises_no_grupo: Quantos países o grupo tem naquele ano (D-063).
-- Coluna cobertura_pct: Países com valor, em % do grupo (D-063).
-- Coluna cobertura_baixa: true quando menos de 50% dos países têm valor (D-063).
-- Coluna valores_fora_da_media: Quantos valores deste grupo não entram em media_sem_atipicos (D-062).
-- Coluna casas_decimais: Casas sugeridas pela API para exibir o valor (D-047).
with base as (
    select
        f.ano,
        f.indicador_id,
        f.casas_decimais,
        p.regiao_id,
        c.nivel_renda_id,
        f.valor,
        a.pais_iso3 is not null as fora_da_media
    from silver.fato_observacao as f
    join silver.dim_pais as p on p.pais_iso3 = f.pais_iso3 and not p.e_agregado
    left join silver.classificacao_renda_anual as c
        on c.pais_iso3 = f.pais_iso3 and c.ano_referencia = f.ano
    left join silver.valor_atipico as a
        on a.pais_iso3 = f.pais_iso3
        and a.indicador_id = f.indicador_id
        and a.ano = f.ano
        and a.fora_da_media
),
resumo as (
    select
        case
            when grouping(nivel_renda_id) = 0 and grouping(regiao_id) = 0 then 'renda_regiao'
            when grouping(nivel_renda_id) = 0 then 'renda'
            when grouping(regiao_id) = 0 then 'regiao'
            else 'mundo'
        end as recorte,
        ano,
        indicador_id,
        nivel_renda_id,
        regiao_id,
        avg(valor) as media,
        avg(valor) filter (where not fora_da_media) as media_sem_atipicos,
        (percentile_cont(0.5) within group (order by valor::double precision))::numeric as mediana,
        count(valor) as paises_com_valor,
        count(*) as paises_no_grupo,
        count(*) filter (where fora_da_media and valor is not null) as valores_fora_da_media,
        max(casas_decimais) as casas_decimais
    from base
    group by grouping sets (
        (ano, indicador_id, nivel_renda_id, regiao_id),
        (ano, indicador_id, nivel_renda_id),
        (ano, indicador_id, regiao_id),
        (ano, indicador_id)
    )
    having grouping(nivel_renda_id) = 1 or nivel_renda_id is not null
)
select
    s.recorte,
    s.ano,
    s.indicador_id,
    i.nome as indicador,
    s.nivel_renda_id,
    n.nome as nivel_renda,
    n.ordem as nivel_renda_ordem,
    s.regiao_id,
    r.nome as regiao,
    s.media,
    s.media_sem_atipicos,
    s.mediana,
    s.paises_com_valor,
    s.paises_no_grupo,
    round(100.0 * s.paises_com_valor / s.paises_no_grupo, 1) as cobertura_pct,
    s.paises_com_valor < s.paises_no_grupo * 0.5 as cobertura_baixa,
    s.valores_fora_da_media,
    s.casas_decimais
from resumo as s
join silver.dim_indicador as i on i.indicador_id = s.indicador_id
left join silver.dim_nivel_renda as n on n.nivel_renda_id = s.nivel_renda_id
left join silver.dim_regiao as r on r.regiao_id = s.regiao_id;
