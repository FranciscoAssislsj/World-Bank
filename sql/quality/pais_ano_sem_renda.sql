-- pergunta: Quais pares de país real e ano do período não têm classificação de renda?
-- severidade: aviso
-- grupo: geral
-- origem: silver.pais, silver.classificacao_renda_anual
-- decisao: D-039
select p.pais_iso3, y.ano
from silver.pais p
cross join generate_series(%(start_year)s::int, %(end_year)s::int) as y (ano)
left join silver.classificacao_renda_anual c
    on c.pais_iso3 = p.pais_iso3 and c.ano_referencia = y.ano
where not p.e_agregado and c.pais_iso3 is null;
