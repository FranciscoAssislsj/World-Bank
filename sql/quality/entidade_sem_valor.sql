-- pergunta: Algum país ou agregado não tem nenhum valor?
-- severidade: aviso
-- grupo: geral
-- origem: silver.observacao
-- decisao: D-042
select pais_iso3, count(*) as linhas
from silver.observacao
group by pais_iso3
having count(valor) = 0;
