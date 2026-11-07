-- gold.fato_observacao
-- Pergunta de negócio: Qual o valor de cada indicador, em cada país ou agregado, em cada ano?
-- Grão (o que é uma linha): o valor de um indicador para um país ou agregado em um ano.
-- Origem: silver.observacao
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). Valor ausente fica NULL (D-042). Ao somar, filtre dim_pais.e_agregado (D-040).
-- Chave: pais_iso3, indicador_id, ano
-- Coluna pais_iso3: País ou agregado medido.
-- Coluna indicador_id: Indicador medido.
-- Coluna ano: Ano da observação.
-- Coluna valor: Valor medido, sem arredondamento; NULL quando a fonte não tem o dado (D-042).
-- Coluna casas_decimais: Casas decimais sugeridas pela fonte (D-047).
select
    pais_iso3,
    indicador_id,
    ano,
    valor,
    casas_decimais
from silver.observacao;
