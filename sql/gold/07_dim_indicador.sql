-- gold.dim_indicador
-- Pergunta de negócio: Quais indicadores são medidos, e de que fonte?
-- Grão (o que é uma linha): uma série de dados.
-- Origem: silver.indicador, silver.nome_portugues
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). Nome em português, com o original preservado (D-082).
-- Chave: indicador_id
-- Coluna indicador_id: Código do indicador.
-- Coluna nome: Nome em português (D-082).
-- Coluna nome_original: Nome como veio da API.
-- Coluna fonte_id: Base de onde vem.
-- Coluna descricao: Descrição do indicador.
-- Coluna organizacao_fonte: Organização que produz o dado.
select
    indicador_id,
    silver.nome_pt('indicador', indicador_id, nome) as nome,
    nome as nome_original,
    fonte_id,
    descricao,
    organizacao_fonte
from silver.indicador;
