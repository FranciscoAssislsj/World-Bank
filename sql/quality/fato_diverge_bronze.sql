-- pergunta: Algum valor do período difere da carga mais recente da bronze?
-- severidade: erro
-- grupo: fato
-- origem: bronze.api_response, silver.observacao
-- decisao: D-043
with ultima as (
    select endpoint, max(ingested_at) as ingested_at
    from bronze.api_response
    where endpoint = any(%(endpoints)s) and params ->> 'date' = %(period)s
    group by endpoint
),
registros as (
    select
        r #>> '{country,id}' as pais_iso2,
        r #>> '{indicator,id}' as indicador_id,
        (r ->> 'date')::smallint as ano,
        (r ->> 'value')::numeric as valor
    from bronze.api_response a
    join ultima u on u.endpoint = a.endpoint and u.ingested_at = a.ingested_at
    cross join lateral jsonb_array_elements(a.payload -> 1) r
    where a.params ->> 'date' = %(period)s
)
select b.pais_iso2, b.indicador_id, b.ano, b.valor as valor_bronze, f.valor as valor_silver
from registros b
left join silver.pais p on p.pais_iso2 = b.pais_iso2
left join silver.observacao f
    on f.pais_iso3 = p.pais_iso3
    and f.indicador_id = b.indicador_id
    and f.ano = b.ano
where f.pais_iso3 is null or f.valor is distinct from b.valor;
