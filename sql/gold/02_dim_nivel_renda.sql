-- gold.dim_nivel_renda
-- Pergunta de negócio: Quais níveis de renda existem, e em que ordem?
-- Grão (o que é uma linha): um nível de renda ou um agrupamento de níveis.
-- Origem: silver.nivel_renda, silver.nome_portugues
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). Nome em português, com o original preservado (D-082).
-- Chave: nivel_renda_id
-- Coluna nivel_renda_id: Código do nível de renda na API.
-- Coluna nome: Nome em português (D-082).
-- Coluna nome_original: Nome como veio da API.
-- Coluna nivel_renda_iso2: Código ISO2 do nível.
-- Coluna ordem: Ordem do menor para o maior; NULL em agrupamentos (D-034).
-- Coluna e_agrupamento: true quando junta outros níveis, para não contar em dobro (D-034).
select
    nivel_renda_id,
    silver.nome_pt('renda', nivel_renda_id, nome) as nome,
    nome as nome_original,
    nivel_renda_iso2,
    ordem,
    e_agrupamento
from silver.nivel_renda;
