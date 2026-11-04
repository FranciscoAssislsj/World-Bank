-- pergunta: A expectativa de vida está fora de 0 a 120 anos?
-- severidade: erro
-- grupo: fato
-- origem: silver.fato_observacao
-- decisao: D-053
select pais_iso3, indicador_id, ano, valor
from silver.fato_observacao
where indicador_id = 'SP.DYN.LE00.IN'
  and (valor <= 0 or valor > 120);
