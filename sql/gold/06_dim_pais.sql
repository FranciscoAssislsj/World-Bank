-- gold.dim_pais
-- Pergunta de negócio: Quais países e agregados existem, e a que grupos pertencem?
-- Grão (o que é uma linha): um país ou um agregado.
-- Origem: silver.pais, silver.nome_portugues
-- Regras: A estrela da gold: lê a silver já tratada, sem regra nova (D-087). Nome em português, com o original preservado (D-082). Ao somar, filtre e_agregado (D-040).
-- Chave: pais_iso3
-- Coluna pais_iso3: Código ISO3 do país ou agregado.
-- Coluna nome: Nome em português (D-082).
-- Coluna nome_original: Nome como veio da API.
-- Coluna pais_iso2: Código ISO2.
-- Coluna regiao_id: Região geográfica atual; NULL em agregados (D-017).
-- Coluna nivel_renda_atual_id: Nível de renda atual; NULL em agregados (D-017, D-025).
-- Coluna tipo_emprestimo_atual_id: Tipo de empréstimo atual; NULL em agregados (D-017, D-025).
-- Coluna regiao_administrativa_id: Região administrativa do World Bank (D-034).
-- Coluna capital: Capital.
-- Coluna latitude: Latitude.
-- Coluna longitude: Longitude.
-- Coluna e_agregado: true para agregado, false para país (D-017).
-- Coluna tipo_agregado: Tipo do agregado; NULL em países (D-034).
select
    pais_iso3,
    silver.nome_pt(case when e_agregado then 'agregado' else 'pais' end, pais_iso3, nome) as nome,
    nome as nome_original,
    pais_iso2,
    regiao_id,
    nivel_renda_atual_id,
    tipo_emprestimo_atual_id,
    regiao_administrativa_id,
    capital,
    latitude,
    longitude,
    e_agregado,
    tipo_agregado
from silver.pais;
