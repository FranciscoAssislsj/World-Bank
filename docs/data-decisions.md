# Decisões sobre o dado

Cada decisão que muda **qual dado entra, como ele é tratado ou como é agregado** fica registrada aqui com o motivo. Os arquivos `.sql` em `sql/gold/` citam o identificador da decisão (ex.: `D-003`) quando aplicam a regra.

| ID | Fase | Decisão | Motivo | Alternativa descartada |
|---|---|---|---|---|
| D-001 | 0 | Usar a fonte **WDI** (`source=2`) para as observações. | É a base principal e mais completa do World Bank, com cobertura por país e por ano para todos os indicadores escolhidos. | Misturar várias fontes, como a International Debt Statistics: os códigos e a cobertura variam, e a comparação entre países fica mais difícil. |
| D-002 | 0 | Período padrão **2000–2024**, configurável em `configs/*.toml` e por `--start`/`--end`. | Antes de 2000 vários indicadores sociais (internet, pobreza, Gini) quase não têm dados. 2024 é o último ano com cobertura razoável. | Usar `date=all` (1960 em diante): aumenta o volume com séries quase todas nulas. |
| D-003 | 0 | Usar o código de CO₂ per capita **`EN.GHG.CO2.PC.CE.AR5`** no lugar de `EN.ATM.CO2E.PC`. | O código antigo foi descontinuado pela API. A confirmação via `/v2/indicator/{id}` fica para a Fase 2. | Manter o código antigo: a API devolveria erro ou uma série vazia. |
| D-004 | 0 | Lista inicial de **15 indicadores**, cobrindo população, economia, pobreza, saúde, educação, infraestrutura e meio ambiente. | Respondem às perguntas de negócio do plano (PIB per capita × expectativa de vida, crescimento, pobreza/Gini, reconciliação de população). | Carregar todos os ~1.400 indicadores do WDI: volume grande, sem pergunta de negócio que use a maioria deles. |
