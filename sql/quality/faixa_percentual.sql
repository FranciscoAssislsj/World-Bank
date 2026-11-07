-- pergunta: Algum percentual está fora de 0 a 100?
-- severidade: erro
-- grupo: fato
-- origem: silver.observacao
-- decisao: D-053
select pais_iso3, indicador_id, ano, valor
from silver.observacao
where indicador_id in (
    'EG.ELC.ACCS.ZS', 'IT.NET.USER.ZS', 'SE.ADT.LITR.ZS', 'SH.XPD.CHEX.GD.ZS',
    'SI.POV.DDAY', 'SI.POV.GINI', 'SL.UEM.TOTL.ZS', 'SP.URB.TOTL.IN.ZS'
)
  and (valor < 0 or valor > 100);
