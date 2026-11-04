-- pergunta: O CO2 per capita é negativo?
-- severidade: erro
-- grupo: fato
-- origem: silver.fato_observacao
-- decisao: D-053
select pais_iso3, indicador_id, ano, valor
from silver.fato_observacao
where indicador_id = 'EN.GHG.CO2.PC.CE.AR5'
  and valor < 0;
