-- gold.ponte_indicador_topico
-- Pergunta de negócio: Em quais temas cada indicador está?
-- Grão (o que é uma linha): a ligação entre um indicador e um tema.
-- Origem: silver.indicador_topico
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087).
-- Chave: indicador_id, topico_id
-- Coluna indicador_id: Indicador.
-- Coluna topico_id: Tema.
select
    indicador_id,
    topico_id
from silver.indicador_topico;
