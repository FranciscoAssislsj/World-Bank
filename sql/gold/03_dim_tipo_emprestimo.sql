-- gold.dim_tipo_emprestimo
-- Pergunta de negócio: Quais tipos de empréstimo existem?
-- Grão (o que é uma linha): um tipo de empréstimo do World Bank.
-- Origem: silver.tipo_emprestimo
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087).
-- Chave: tipo_emprestimo_id
-- Coluna tipo_emprestimo_id: Código do tipo na API.
-- Coluna nome: Nome como veio da API.
-- Coluna tipo_emprestimo_iso2: Código ISO2 do tipo.
select
    tipo_emprestimo_id,
    nome,
    tipo_emprestimo_iso2
from silver.tipo_emprestimo;
