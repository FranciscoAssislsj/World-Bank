-- pergunta: A renda atual de dim_pais difere do ano mais recente do histórico?
-- severidade: aviso
-- grupo: geral
-- origem: silver.dim_pais, silver.classificacao_renda_anual
-- decisao: D-038
select p.pais_iso3, p.nivel_renda_atual_id, c.nivel_renda_id as nivel_no_historico, c.ano_referencia
from silver.dim_pais p
join silver.classificacao_renda_anual c on c.pais_iso3 = p.pais_iso3
where c.ano_referencia = (
    select max(ano_referencia) from silver.classificacao_renda_anual
)
  and c.nivel_renda_id <> p.nivel_renda_atual_id;
