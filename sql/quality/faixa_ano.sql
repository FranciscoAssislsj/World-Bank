-- pergunta: Algum ano está fora de 1960 até o ano atual?
-- severidade: erro
-- grupo: fato
-- origem: silver.observacao
-- decisao: D-053
select pais_iso3, indicador_id, ano
from silver.observacao
where ano < 1960 or ano > extract(year from current_date);
