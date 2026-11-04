-- pergunta: Alguma execução está como running há mais de 1 hora?
-- severidade: aviso
-- grupo: geral
-- origem: etl.pipeline_run
-- decisao: D-046
select run_id, pipeline, started_at
from etl.pipeline_run
where status = 'running' and started_at < now() - interval '1 hour';
