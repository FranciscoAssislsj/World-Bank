-- pergunta: Há país ou indicador que sumiu da carga mais recente da bronze?
-- severidade: aviso
-- grupo: geral
-- origem: bronze.api_response, silver.pais, silver.indicador
-- decisao: D-021
select 'pais' as tipo, p.pais_iso3 as codigo
from silver.pais p
where not exists (
    select 1
    from bronze.api_response a
    cross join lateral jsonb_array_elements(a.payload -> 1) r
    where a.endpoint = 'country'
      and a.ingested_at = (
          select max(ingested_at) from bronze.api_response where endpoint = 'country'
      )
      and r ->> 'id' = p.pais_iso3
)
union all
select 'indicador', i.indicador_id
from silver.indicador i
where not exists (
    select 1 from bronze.api_response a
    where a.endpoint = 'indicator/' || i.indicador_id
);
