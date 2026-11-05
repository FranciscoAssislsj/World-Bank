-- gold.reconciliacao_agregados
-- Pergunta de negócio: A soma dos países bate com o número oficial do World Bank?
-- Grão (o que é uma linha): um agregado (região, nível de renda ou mundo), um indicador somável e um ano.
-- Origem: silver.nome_portugues, silver.fato_observacao, silver.dim_pais, silver.dim_nivel_renda, silver.dim_indicador
-- Regras: Nomes em português, com o original guardado na silver (D-082). só população e PIB, os indicadores que podem ser somados. A renda é a atual, como o World Bank calcula (D-066). A soma usa todos os valores da silver, porque o número oficial os inclui (D-062). A tolerância é de 2% (D-066).
-- Chave: agregado_id, indicador_id, ano
-- Coluna agregado_id: Código do agregado na API.
-- Coluna agregado: Nome do agregado em português (D-082).
-- Coluna tipo: regiao, renda ou mundo.
-- Coluna indicador_id: Código do indicador.
-- Coluna indicador: Nome do indicador em português (D-082).
-- Coluna ano: Ano da observação.
-- Coluna soma_paises: Soma calculada a partir dos países.
-- Coluna valor_oficial: Valor do agregado publicado pela API.
-- Coluna diferenca: soma_paises menos valor_oficial.
-- Coluna diferenca_pct: A diferença, em % do valor oficial.
-- Coluna paises_sem_valor: Países do grupo sem dado; explica boa parte da diferença no PIB (D-066).
-- Coluna dentro_da_tolerancia: true quando a diferença é de até 2%; false também se faltar o oficial (D-066).
with grupos as (
    select pais_iso3, regiao_id as agregado_id, 'regiao' as tipo
    from silver.dim_pais
    where not e_agregado
    union all
    select p.pais_iso3, p.nivel_renda_atual_id, 'renda'
    from silver.dim_pais as p
    join silver.dim_nivel_renda as n
        on n.nivel_renda_id = p.nivel_renda_atual_id and n.ordem is not null
    where not p.e_agregado
    union all
    select pais_iso3, 'WLD', 'mundo'
    from silver.dim_pais
    where not e_agregado
),
soma as (
    select
        g.agregado_id,
        g.tipo,
        f.indicador_id,
        f.ano,
        sum(f.valor) as soma_paises,
        count(*) - count(f.valor) as paises_sem_valor
    from grupos as g
    join silver.fato_observacao as f on f.pais_iso3 = g.pais_iso3
    where f.indicador_id in ('SP.POP.TOTL', 'NY.GDP.MKTP.CD')
    group by g.agregado_id, g.tipo, f.indicador_id, f.ano
)
select
    s.agregado_id,
    silver.nome_pt('agregado', s.agregado_id, a.nome) as agregado,
    s.tipo,
    s.indicador_id,
    silver.nome_pt('indicador', i.indicador_id, i.nome) as indicador,
    s.ano,
    s.soma_paises,
    o.valor as valor_oficial,
    s.soma_paises - o.valor as diferenca,
    100 * (s.soma_paises - o.valor) / nullif(o.valor, 0) as diferenca_pct,
    s.paises_sem_valor,
    coalesce(abs(s.soma_paises - o.valor) <= 0.02 * o.valor, false) as dentro_da_tolerancia
from soma as s
join silver.dim_pais as a on a.pais_iso3 = s.agregado_id
join silver.dim_indicador as i on i.indicador_id = s.indicador_id
left join silver.fato_observacao as o
    on o.pais_iso3 = s.agregado_id
    and o.indicador_id = s.indicador_id
    and o.ano = s.ano;
