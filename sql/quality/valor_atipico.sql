-- pergunta: Há valor improvável, que merece investigação?
-- severidade: aviso
-- grupo: geral
-- origem: silver.fato_observacao
-- decisao: D-052
select 'expectativa de vida abaixo de 30' as motivo, pais_iso3, ano, valor
from silver.fato_observacao
where indicador_id = 'SP.DYN.LE00.IN' and valor < 30
union all
select 'CO2 per capita acima de 60', pais_iso3, ano, valor
from silver.fato_observacao
where indicador_id = 'EN.GHG.CO2.PC.CE.AR5' and valor > 60
union all
select 'população variou mais de 20 por cento em um ano', pais_iso3, ano, valor
from (
    select
        pais_iso3,
        ano,
        valor,
        lag(valor) over (partition by pais_iso3 order by ano) as valor_anterior
    from silver.fato_observacao
    where indicador_id = 'SP.POP.TOTL'
) s
where valor_anterior > 0 and abs(valor / valor_anterior - 1) > 0.2;
