-- pergunta: População, PIB ou PIB per capita são zero ou negativos?
-- severidade: erro
-- grupo: fato
-- origem: silver.fato_observacao
-- decisao: D-053
select pais_iso3, indicador_id, ano, valor
from silver.fato_observacao
where indicador_id in ('SP.POP.TOTL', 'NY.GDP.MKTP.CD', 'NY.GDP.PCAP.CD')
  and valor <= 0;
