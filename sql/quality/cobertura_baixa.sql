-- pergunta: Algum indicador tem valor em menos da metade dos países em um ano?
-- severidade: aviso
-- grupo: geral
-- origem: silver.fato_observacao, silver.dim_pais
-- decisao: D-042
select f.indicador_id, f.ano, count(f.valor) as paises_com_valor, count(*) as paises
from silver.fato_observacao f
join silver.dim_pais p using (pais_iso3)
where not p.e_agregado
  and f.indicador_id = any(%(indicators)s)
  and f.ano between %(start_year)s and %(end_year)s
group by f.indicador_id, f.ano
having count(f.valor) < count(*) * 0.5;
