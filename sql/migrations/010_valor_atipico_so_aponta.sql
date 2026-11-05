-- 010_valor_atipico_so_aponta.sql
-- O projeto usa uma média só, com os valores da silver: um valor atípico é apontado,
-- mas não sai de nenhuma conta (D-062, D-070). Tirar uma coluna exige recriar a view,
-- e as views da gold que dependem dela voltam no próximo build-gold.

drop materialized view if exists gold.pais_ano;
drop materialized view if exists gold.resumo_renda_regiao;
drop materialized view if exists gold.ranking_crescimento;
drop materialized view if exists gold.valores_atipicos;
drop view silver.valor_atipico;

create view silver.valor_atipico as
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'expectativa de vida abaixo de 30'::text as motivo,
    'mantido em todas as contas: a fonte concentra as mortes de uma crise em um único ano'::text
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
    'mantido em todas as contas: as bases de emissões divergem, e o valor pesa na média do grupo'
from silver.fato_observacao
where indicador_id = 'EN.GHG.CO2.PC.CE.AR5' and valor > 60
union all
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    'população variou mais de 20 por cento em um ano',
    'mantido em todas as contas, inclusive no ranking de população urbana'
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
comment on column silver.valor_atipico.tratamento is 'O que é feito com o valor, em uma frase.';
