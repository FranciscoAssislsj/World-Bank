-- 008_valor_atipico.sql
-- silver.valor_atipico: a definição única de valor atípico, lida pela regra de
-- qualidade e pela gold (D-062). É uma view: os valores da silver não mudam (D-052).

create view silver.valor_atipico as
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'expectativa de vida abaixo de 30'::text as motivo,
    true as sai_da_analise,
    'fora da análise: a fonte concentra as mortes de uma crise em um único ano'::text
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
    'fora da análise: as bases de emissões divergem, e a magnitude não é confiável'
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
    'mantido: o valor pode estar certo; o país só sai do ranking de população urbana se o salto cair na janela'
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

comment on view silver.valor_atipico is
    'Uma linha = um valor apontado como estranho, com o motivo e o tratamento (D-062).';
comment on column silver.valor_atipico.pais_iso3 is 'País ou agregado do valor.';
comment on column silver.valor_atipico.indicador_id is 'Indicador do valor.';
comment on column silver.valor_atipico.ano is 'Ano do valor.';
comment on column silver.valor_atipico.valor is 'O valor como está em fato_observacao.';
comment on column silver.valor_atipico.motivo is 'O limite que o valor ultrapassou.';
comment on column silver.valor_atipico.sai_da_analise is
    'true: a gold não usa o valor nas estatísticas. false: é só apontado (D-062).';
comment on column silver.valor_atipico.tratamento is 'O que é feito com o valor, em uma frase.';
