-- gold.dim_regiao
-- Pergunta de negócio: Quais regiões e agrupamentos existem?
-- Grão (o que é uma linha): uma região geográfica ou um agrupamento de países.
-- Origem: silver.regiao, silver.nome_portugues
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). Nome em português, com o original preservado (D-082).
-- Chave: regiao_id
-- Coluna regiao_id: Código da região na API.
-- Coluna nome: Nome em português (D-082).
-- Coluna nome_original: Nome como veio da API.
-- Coluna regiao_iso2: Código ISO2 da região.
-- Coluna e_geografica: true para região geográfica, false para agrupamento administrativo.
select
    regiao_id,
    silver.nome_pt('regiao', regiao_id, nome) as nome,
    nome as nome_original,
    regiao_iso2,
    e_geografica
from silver.regiao;
