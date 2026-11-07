-- pergunta: Falta linha de algum país real, indicador ou ano do período?
-- severidade: erro
-- grupo: fato
-- origem: silver.pais, silver.observacao
-- decisao: D-040
select p.pais_iso3, i.indicador_id, y.ano
from silver.pais p
cross join unnest(%(indicators)s::text[]) as i (indicador_id)
cross join generate_series(%(start_year)s::int, %(end_year)s::int) as y (ano)
left join silver.observacao f
    on f.pais_iso3 = p.pais_iso3
    and f.indicador_id = i.indicador_id
    and f.ano = y.ano
where not p.e_agregado and f.pais_iso3 is null;
