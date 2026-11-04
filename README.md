# World-Bank

Pipeline de dados que consome a [World Bank Indicators API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) e organiza os dados em **arquitetura medalhão** (`bronze` → `silver` → `gold`) no **PostgreSQL**, com dashboards em Streamlit e Power BI.

> Em construção. A documentação completa (tabelas, indicadores, dashboards e a seção "Onde a IA errou") entra na fase final.

**Rastreabilidade:** cada indicador da camada gold sai de um arquivo em `sql/gold/`, cada decisão sobre o dado tem motivo em [docs/data-decisions.md](docs/data-decisions.md), os erros da IA ficam em [docs/ai-log.md](docs/ai-log.md), e o histórico do git tem um commit por etapa.

**Fonte dos dados:** World Bank, World Development Indicators e histórico de classificação de renda (`OGHIST`), sob licença [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by).

## Como rodar do zero

Pré-requisitos: [pyenv](https://github.com/pyenv-win/pyenv-win) com Python 3.14, [uv](https://docs.astral.sh/uv/) e Docker.

```bash
uv sync                      # cria a .venv e instala as dependências do uv.lock
cp .env.example .env         # depois, ajuste os valores locais
docker compose up -d --wait  # sobe o PostgreSQL 17 em 127.0.0.1:5433
uv run python -m world_bank migrate      # cria os schemas e as tabelas
uv run python -m world_bank load-bronze  # grava na bronze as respostas da API e o histórico de renda
uv run python -m world_bank load-dimensions  # grava as tabelas da silver a partir da bronze
```

O banco fica na porta **5433** do computador, e não na 5432, para não conflitar com um PostgreSQL já instalado.

`load-bronze` aceita `--start` e `--end` para mudar o período das observações (padrão: 2000–2024). Rodar de novo só grava as requisições cujo conteúdo mudou na API ([D-010](docs/data-decisions.md)).

| Tabela | Uma linha é |
|---|---|
| `bronze.api_response` | uma página de resposta da API, com o JSON original em `payload` |
| `bronze.source_file` | uma versão de um arquivo baixado fora da API, sem alteração |
| `silver.dim_regiao` | uma região geográfica ou um agrupamento de países |
| `silver.dim_nivel_renda` | um nível de renda ou um agrupamento de níveis |
| `silver.dim_tipo_emprestimo` | um tipo de empréstimo do World Bank |
| `silver.dim_pais` | um país ou um agregado |
| `silver.classificacao_renda_anual` | a classificação oficial de renda de um país em um ano |
| `silver.dim_fonte` | uma base de dados do World Bank |
| `silver.dim_topico` | um tema dos indicadores |
| `silver.dim_indicador` | uma série de dados |
| `silver.ponte_indicador_topico` | a ligação entre um indicador e um tema |
| `etl.schema_migrations` | uma migração de `sql/migrations/` já aplicada |

## Modelo de dados

![Diagrama da camada silver: dim_pais liga-se a dim_regiao, dim_nivel_renda, dim_tipo_emprestimo e classificacao_renda_anual; dim_indicador liga-se a dim_fonte e, pela ponte_indicador_topico, a dim_topico.](docs/modelagem-silver.svg)

Os dois grupos ainda não se ligam: a tabela de observações, a próxima etapa, vai conectar países e indicadores.

As colunas de cada tabela, com tipo de valor e descrição, estão no [dicionário de dados](docs/dicionario-dados.md).

## Testes e qualidade

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest                # testes unitários: sem rede e sem banco, cobertura >= 70%
uv run pytest -m integration # testes contra o PostgreSQL local
```
