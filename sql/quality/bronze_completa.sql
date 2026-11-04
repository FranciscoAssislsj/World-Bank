-- pergunta: Alguma carga tem menos páginas ou registros do que a API informou?
-- severidade: erro
-- grupo: geral
-- origem: bronze.api_response
-- decisao: D-011
select
    endpoint,
    ingested_at,
    count(*) as paginas_gravadas,
    max(pages) as paginas_informadas,
    sum(record_count) as registros_gravados,
    max(total) as registros_informados
from bronze.api_response
group by endpoint, params_hash, ingested_at
having count(*) <> max(pages) or sum(record_count) <> max(total);
