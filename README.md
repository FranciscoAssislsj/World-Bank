# World-Bank

Pipeline de dados que consome a [World Bank Indicators API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) e organiza os dados em **arquitetura medalhão** (`bronze` → `silver` → `gold`) no **PostgreSQL**, com dashboards em Streamlit e Power BI.

> Em construção. A documentação completa (tabelas, indicadores, dashboards e a seção "Onde a IA errou") entra na fase final.

**Rastreabilidade:** cada indicador da camada gold sai de um arquivo em `sql/gold/`, cada decisão sobre o dado tem motivo em [docs/data-decisions.md](docs/data-decisions.md), os erros da IA ficam em [docs/ai-log.md](docs/ai-log.md), e o histórico do git tem um commit por etapa.

**Fonte dos dados:** World Bank, World Development Indicators, sob licença [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by).

## Como rodar do zero

Pré-requisitos: [pyenv](https://github.com/pyenv-win/pyenv-win) com Python 3.14, [uv](https://docs.astral.sh/uv/) e Docker.

```bash
uv sync                      # cria a .venv e instala as dependências do uv.lock
cp .env.example .env         # depois, ajuste os valores locais
docker compose up -d --wait  # sobe o PostgreSQL 17 em localhost:5433
uv run python -m world_bank migrate      # cria os schemas e as tabelas
uv run python -m world_bank load-bronze  # grava as respostas da API em bronze.api_response
```

O banco fica na porta **5433** do computador, e não na 5432, para não conflitar com um PostgreSQL já instalado.

`load-bronze` aceita `--start` e `--end` para mudar o período das observações (padrão: 2000–2024). Rodar de novo só grava as requisições cujo conteúdo mudou na API ([D-010](docs/data-decisions.md)).

| Tabela | Uma linha é |
|---|---|
| `bronze.api_response` | uma página de resposta da API, com o JSON original em `payload` |
| `etl.schema_migrations` | uma migração de `sql/migrations/` já aplicada |

## Testes e qualidade

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest                # testes unitários: sem rede e sem banco, cobertura >= 70%
uv run pytest -m integration # testes contra o PostgreSQL local
```
