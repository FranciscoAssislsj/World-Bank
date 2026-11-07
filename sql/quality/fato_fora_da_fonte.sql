-- pergunta: Há linha do fato no período que sumiu da bronze?
-- severidade: aviso
-- grupo: geral
-- origem: bronze.api_response, silver.observacao
-- decisao: D-021
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
select f.pais_iso3, f.indicador_id, f.ano
from silver.observacao f
join silver.pais p using (pais_iso3)
where f.indicador_id = any(%(indicators)s)
  and f.ano between %(start_year)s and %(end_year)s
  and not exists (
      select 1 from registros b
      where b.pais_iso2 = p.pais_iso2
        and b.indicador_id = f.indicador_id
        and b.ano = f.ano
  );
