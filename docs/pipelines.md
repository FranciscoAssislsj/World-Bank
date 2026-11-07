# Pipelines

Todo comando roda com `uv run python -m world_bank <comando>`, e cada execução fica registrada em `etl.pipeline_run` ([D-046](data-decisions.md)).

## Os comandos

| Comando | Lê de | Grava em | Rodar de novo |
|---|---|---|---|
| `migrate` | `sql/migrations/` | estrutura do banco, `etl.schema_migrations` | só aplica o que falta |
| `load-bronze` | API do World Bank e arquivo `OGHIST` | `bronze.api_response`, `bronze.source_file` | só grava o que mudou na fonte ([D-010](data-decisions.md)) |
| `load-dimensions` | bronze | cadastros da silver e `silver.classificacao_renda_anual` | atualiza sem duplicar |
| `load-observations` | bronze | `silver.observacao` | é pulado se a bronze não mudou ([D-045](data-decisions.md)) |
| `validate` | silver, bronze e `etl.pipeline_run` | `etl.quality_check` | não altera os dados |
| `build-gold` | `sql/gold/` | todas as tabelas da gold | recria tudo |
| `run-all` | todos acima | todos acima | para na primeira falha |

## A ordem importa

```bash
uv run python -m world_bank migrate
uv run python -m world_bank load-bronze
uv run python -m world_bank load-dimensions
uv run python -m world_bank load-observations
uv run python -m world_bank validate
uv run python -m world_bank build-gold
```

O `run-all` roda essa mesma sequência. O `validate` vem antes do `build-gold` para que uma regra de erro impeça a publicação ([D-068](data-decisions.md)).

## Opções

| Opção | Aceita em | O que faz |
|---|---|---|
| `--start`, `--end` | `load-bronze`, `load-observations`, `validate`, `run-all` | mudam o período, que por padrão é 2000 a 2024 |
| `--full-refresh` | `load-observations`, `run-all` | processa de novo as observações, mesmo que a bronze não tenha mudado |

Use o mesmo período na bronze e nas observações: a silver lê só as cargas do período pedido ([D-044](data-decisions.md)).

## Quando algo dá errado

- **Na API:** erro temporário é repetido com espera crescente. Código de indicador inválido faz a execução falhar, em vez de pular o indicador em silêncio ([D-006](data-decisions.md)).
- **Na bronze:** as páginas de uma requisição são gravadas juntas, ou nenhuma ([D-011](data-decisions.md)).
- **Nas observações:** o dado é gravado e conferido na mesma transação, e um erro desfaz tudo ([D-050](data-decisions.md)).
- **Na gold:** se a recriação falhar, as tabelas anteriores continuam valendo ([D-056](data-decisions.md)).

## Perguntas que a gold responde

Cada arquivo traz a pergunta no cabeçalho.

| Tabela | Pergunta de negócio |
|---|---|
| [`gold.pais_ano`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/20_pais_ano.sql) | Como PIB per capita, expectativa de vida, eletricidade e internet se relacionam em cada país e ano? |
| [`gold.resumo_renda_regiao`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/21_resumo_renda_regiao.sql) | Como cada indicador evolui por nível de renda e por região, incluindo pobreza e desigualdade? |
| [`gold.resumo_anual`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/22_resumo_anual.sql) | Em cada ano, quantos países têm dado, quanto a renda muda a expectativa de vida, quem tem o maior PIB e onde o Brasil está? |
| [`gold.ranking_crescimento`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/23_ranking_crescimento.sql) | Quais países mais cresceram na última década, em PIB real e em população urbana, por região? |
| [`gold.reconciliacao_agregados`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/24_reconciliacao_agregados.sql) | A soma dos países bate com o número oficial do World Bank? |
| [`gold.valores_atipicos`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/11_valores_atipicos.sql) | Quais valores foram apontados como estranhos, e o que foi feito com cada um? |

!!! warning "Filtre o recorte"
    `gold.resumo_renda_regiao` tem linhas por renda, por região, por renda e região, e do mundo. Filtre a coluna `recorte`, para não contar em dobro ([D-060](data-decisions.md)).
