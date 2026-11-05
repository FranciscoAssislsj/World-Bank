-- 009_valor_atipico_media_ajustada.sql
-- Os valores atípicos ficam na gold com o número da fonte; o que muda é só a média
-- ajustada, oferecida ao lado da média com todos (D-062, D-070).

alter view silver.valor_atipico rename column sai_da_analise to fora_da_media;

create or replace view silver.valor_atipico as
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'expectativa de vida abaixo de 30'::text as motivo,
    true as fora_da_media,
    'fica fora de media_sem_atipicos: a fonte concentra as mortes de uma crise em um único ano'::text
        as tratamento
from silver.fato_observacao
where indicador_id = 'SP.DYN.LE00.IN' and valor < 30
union all
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'CO2 per capita acima de 60',
    true,
    'fica fora de media_sem_atipicos: as bases de emissões divergem, e o valor distorce a média do grupo'
from silver.fato_observacao
where indicador_id = 'EN.GHG.CO2.PC.CE.AR5' and valor > 60
union all
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'população variou mais de 20 por cento em um ano',
    false,
    'entra em todas as médias; o país só sai do ranking de população urbana se o salto cair na janela'
from (
    select
        pais_iso3,
        indicador_id,
        ano,
        valor,
        lag(valor) over (partition by pais_iso3 order by ano) as valor_anterior
    from silver.fato_observacao
    where indicador_id = 'SP.POP.TOTL'
) as populacao
where valor_anterior > 0 and abs(valor / valor_anterior - 1) > 0.2;

comment on column silver.valor_atipico.fora_da_media is
    'true: o valor não entra em media_sem_atipicos. Em todo o resto, ele continua (D-062).';
