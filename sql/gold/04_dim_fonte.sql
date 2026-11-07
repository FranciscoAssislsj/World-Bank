-- gold.dim_fonte
-- Pergunta de negócio: De quais bases do World Bank vêm os dados?
-- Grão (o que é uma linha): uma base de dados do World Bank.
-- Origem: silver.fonte
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087).
-- Chave: fonte_id
-- Coluna fonte_id: Código da base na API.
-- Coluna codigo: Sigla da base.
-- Coluna nome: Nome como veio da API.
-- Coluna conceitos: Quantos conceitos a base tem.
-- Coluna ultima_atualizacao: Data da última atualização informada pela fonte.
-- Coluna tem_dados: true se a base traz dados.
-- Coluna tem_metadados: true se a base traz metadados; NULL se a fonte não informa.
select
    fonte_id,
    codigo,
    nome,
    conceitos,
    ultima_atualizacao,
    tem_dados,
    tem_metadados
from silver.fonte;
