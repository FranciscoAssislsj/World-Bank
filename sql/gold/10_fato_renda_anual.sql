-- gold.fato_renda_anual
-- Pergunta de negócio: Em que nível de renda cada país estava em cada ano?
-- Grão (o que é uma linha): a classificação oficial de renda de um país para um ano.
-- Origem: silver.classificacao_renda_anual
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). É a renda histórica oficial (D-036, D-038).
-- Chave: pais_iso3, ano_referencia
-- Coluna pais_iso3: País classificado.
-- Coluna ano_referencia: Ano da renda usada na classificação; é o ano para ligar às observações (D-038).
-- Coluna ano_fiscal: Ano fiscal do World Bank em que a classificação vigorou.
-- Coluna nivel_renda_id: Nível de renda do país naquele ano.
select
    pais_iso3,
    ano_referencia,
    ano_fiscal,
    nivel_renda_id
from silver.classificacao_renda_anual;
