-- gold.dim_topico
-- Pergunta de negócio: Em quais temas os indicadores se organizam?
-- Grão (o que é uma linha): um tema dos indicadores.
-- Origem: silver.topico
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087).
-- Chave: topico_id
-- Coluna topico_id: Código do tema na API.
-- Coluna nome: Nome como veio da API.
-- Coluna descricao: Descrição do tema.
select
    topico_id,
    nome,
    descricao
from silver.topico;
