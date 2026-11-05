-- gold.valores_atipicos
-- Pergunta de negócio: Quais valores foram apontados como estranhos, e o que foi feito com cada um?
-- Grão (o que é uma linha): um valor apontado, de um país, um indicador e um ano.
-- Origem: silver.valor_atipico, silver.dim_pais, silver.dim_indicador
-- Regras: só países, sem agregados (D-023). É o aviso das remoções, para os dashboards mostrarem (D-062).
-- Chave: pais_iso3, indicador_id, ano
-- Coluna pais_iso3: Código ISO3 do país.
-- Coluna pais: Nome do país.
-- Coluna indicador_id: Código do indicador.
-- Coluna indicador: Nome do indicador, como vem da API.
-- Coluna ano: Ano do valor.
-- Coluna valor_original: O valor como está na silver.
-- Coluna motivo: O limite que o valor ultrapassou.
-- Coluna sai_da_analise: true quando o valor virou NULL em pais_ano e ficou fora de média e mediana (D-062).
-- Coluna tratamento: O que foi feito com o valor, em uma frase.
select
    a.pais_iso3,
    p.nome as pais,
    a.indicador_id,
    i.nome as indicador,
    a.ano,
    a.valor as valor_original,
    a.motivo,
    a.sai_da_analise,
    a.tratamento
from silver.valor_atipico as a
join silver.dim_pais as p on p.pais_iso3 = a.pais_iso3 and not p.e_agregado
join silver.dim_indicador as i on i.indicador_id = a.indicador_id;
