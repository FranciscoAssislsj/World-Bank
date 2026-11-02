# plan.md — Pipeline de dados `world-bank` (World Bank API v2 → PostgreSQL, arquitetura medalhão)

> Ao aprovar este plano, o primeiro passo é salvar este conteúdo como `plan.md` na raiz do repositório.
> Regras de implementação: `SKILL.md`. Referência da API: `doc_api.md`.

## Contexto

O repositório hoje só tem o esqueleto gerado pelo `uv init` (`main.py` com print, `pyproject.toml` sem dependências, `.gitignore` mínimo). O objetivo é construir um pipeline de engenharia de dados de portfólio que consome a **World Bank Indicators API v2**, organiza os dados em **arquitetura medalhão (bronze → silver → gold) no PostgreSQL** (gratuito, local via Docker), modela a silver como **esquema estrela**, entrega indicadores na gold e os exibe em **dois dashboards (Streamlit e Power BI)**. Tudo segue as regras do `SKILL.md` (uv, pyenv/3.14, ruff, pytest ≥ 70%, MkDocs, separação extract/transform/validate/load/pipelines) e os requisitos de entrega do curso.

### Sobre "as 45 tabelas"
A API não tem 45 tabelas: tem **45+ fontes (bases)**, como WDI, International Debt Statistics etc. Cada fonte é um conjunto de *indicadores* (séries temporais). As tabelas do projeto saem dos **endpoints de cadastro** (países, regiões, renda, tipos de empréstimo, fontes, tópicos, indicadores) + o **endpoint de observações**. Isso gera **9 tabelas na silver + 1 de controle**, comparável ao Olist (9), com joins naturais.

### Cenário escolhido
**"Panorama de desenvolvimento socioeconômico mundial (2000–2024)"** usando a fonte **WDI (source=2)**. Perguntas de negócio que a camada gold responde:
1. Como PIB per capita se relaciona com expectativa de vida e acesso a eletricidade/internet, por **nível de renda** e **região**?
2. Quais países mais cresceram (PIB, população urbana) por região na última década?
3. Evolução de pobreza e desigualdade (Gini) em países de renda baixa vs. média.
4. **Check de qualidade cruzado**: soma da população dos países de uma região vs. o agregado oficial da API (ex. `LCN`, `WLD`).

### Requisitos da entrega (curso) → como o plano atende
| Requisito | Atendimento |
|---|---|
| Fonte pública, tema conhecido | World Bank Indicators API v2 (pública, sem chave). Dados sob licença **CC BY 4.0** (citar no README com link). Não é Olist. |
| ≥ 2 tabelas com JOIN | 9 tabelas na `silver` (dimensões + fato); joins fato↔país↔região/renda, fato↔indicador↔tópico. |
| 3 camadas separadas | Medalhão em schemas Postgres: **`bronze`** (JSON da API intacto, só INSERT, nunca UPDATE) → **`silver`** (normalizado/tipado/modelado) → **`gold`** (indicadores). |
| Testes unitários com dado inventado, sem abrir o banco | Fixtures JSON inventadas em `tests/fixtures/`; HTTP mockado com `respx`; carga testada com conexão mockada. Testes que tocam o Postgres ficam só em `-m integration`, fora do `pytest` padrão. |
| Repo público no GitHub pessoal | Criar repo na conta pessoal e configurar `origin` (Fase 0). |
| Commit por etapa | **Cada fase termina em um commit** (ou poucos) com mensagem descrevendo o que mudou. O usuário executa `git add`/`commit`/`push`; a IA só sugere a mensagem. |
| Dashboard | **Streamlit** e **Power BI Desktop**, ambos lendo **só** `gold.*`, sem cálculo na tela. Power BI versionado como `.pbix` + PDF exportado. |
| Seção sobre erros da IA | `docs/ai-log.md` atualizado a cada fase (o que a IA errou/assumiu, como foi descoberto — ex. contagem de linhas antes/depois); resumo curto no fim do README. |
| Pasta da gold com as consultas SQL | `sql/gold/`: **um arquivo `.sql` por view/indicador da gold**, cada um com cabeçalho explicando pergunta de negócio, tabelas de origem, o que é uma linha e regras aplicadas. |
| Decisões sobre o dado com motivo | `docs/data-decisions.md` atualizado a cada fase (decisão → motivo → alternativa descartada → fase). |
| README como porta de entrada | Fonte+licença, o que é uma linha de cada tabela, as 3 camadas e os indicadores, como rodar do zero (incluindo testes), dashboards, seção da IA. |

### Critério principal (checar ao fim de cada fase)
> **Cada indicador tem um arquivo `.sql` de onde saiu, cada decisão sobre o dado tem um motivo escrito, e o histórico do git conta a ordem em que as coisas aconteceram.**

- Indicador → arquivo: toda coluna/métrica da gold é rastreável até um arquivo em `sql/gold/`; nada é calculado em Python, no Streamlit ou no Power BI.
- Decisão → motivo: `docs/data-decisions.md` (sobre o dado) e `docs/ai-log.md` (erros da IA); comentários nos `.sql` apontam para a decisão correspondente.
- Ordem → git: um commit por fase, mensagens descritivas, sem squash.

### Branches
- Todo o trabalho é feito e commitado no branch **`dev`**; a `main` só recebe código com lint e testes passando.
- `dev` → `main` por Pull Request no GitHub com **"Create a merge commit"** (nunca "Squash and merge", que apagaria a ordem dos commits).

### Modo de trabalho: aprendizado
O objetivo também é **aprender os fundamentos**. Em cada passo, antes de implementar, explicar ao usuário:
1. **O quê** será feito e **por quê** (qual problema resolve);
2. **O fundamento** por trás (ex.: arquitetura medalhão, modelo estrela, idempotência, upsert, paginação, retry com backoff, mocks em teste, migrações, variáveis de ambiente);
3. **Alternativas** consideradas e por que não foram escolhidas (curto);
4. **Como conferir** o resultado (comando, contagem de linhas antes/depois, query).

**Quem executa:** os comandos (`uv`, `docker`, `git`, `pytest`, `ruff`, `mkdocs`, Power BI etc.) são executados **pelo usuário**. A IA apresenta o comando, explica o que ele faz e o resultado esperado, e espera o usuário rodar e colar a saída. A IA só executa comandos, cria/edita arquivos ou faz commits **quando o usuário mandar explicitamente**, e essa autorização vale apenas para aquela ação.

Ao fim de cada fase: resumo do que foi aprendido, pausa para dúvidas, registro em `docs/ai-log.md` e `docs/data-decisions.md`, checagem do critério principal e só então o commit da etapa, feito pelo usuário.

## Decisões

| Tema | Decisão |
|---|---|
| Banco | **PostgreSQL 17 em Docker** (`docker-compose.yml`), custo zero. Opcional: Neon/Supabase free tier mudando só `DATABASE_URL`. |
| HTTP | `httpx` (timeout explícito) + `tenacity` (retry/backoff em 5xx, timeout, erro 105/199 no corpo). |
| Validação | `pydantic` para registros da API; checagens explícitas no DataFrame antes da carga. |
| Transformação | `pandas` (funções puras). |
| Carga | `psycopg[binary]` 3: `COPY` para tabela temporária + `INSERT ... ON CONFLICT DO UPDATE` (upsert idempotente). |
| Migrações | SQL puro versionado em `sql/migrations/NNN_*.sql`, aplicado por comando `migrate` (tabela `etl.schema_migrations`). Sem ORM. |
| Config | `pydantic-settings` em `world_bank/config.py`; `WB_ENV` seleciona `configs/{dev,prod}.toml`; segredos (`DATABASE_URL`) só via env/`.env`. |
| CLI | `argparse` em `__main__.py`: `uv run python -m world_bank <comando>`. |
| Dev | `ruff`, `pytest`, `pytest-cov`, `pytest-mock`, `respx`, `mkdocs`, `mkdocs-material`. |
| Dashboards | `streamlit` (grupo `dashboard` do uv) + Power BI Desktop (gratuito, sem publicação online). |

> Validar na Fase 0 que todas as dependências têm wheels para Python 3.14; se alguma não tiver, parar e avisar (SKILL §2).

## Modelo de dados (PostgreSQL, arquitetura medalhão)

Schemas: **`bronze`** (cópia fiel da fonte) → **`silver`** (limpo, tipado, esquema estrela) → **`gold`** (indicadores prontos para consumo), mais **`etl`** para controle.

**O que é uma linha** (vai para o README): `bronze.api_response` = uma página de resposta da API; `silver.dim_country` = um país ou agregado; `silver.dim_indicator` = uma série; `silver.fact_observation` = o valor de um indicador para um país em um período; `gold.country_year_wide` = um país em um ano com todos os indicadores.

| Schema.tabela | Origem (endpoint) | Chave | Relacionamentos |
|---|---|---|---|
| `bronze.api_response` | todas as chamadas | `(endpoint, params_hash, page, ingested_at)` | JSONB da resposta original, append-only |
| `silver.dim_region` | `/v2/region` | `region_id` | — |
| `silver.dim_income_level` | `/v2/incomelevel` | `income_level_id` | — |
| `silver.dim_lending_type` | `/v2/lendingtypes` | `lending_type_id` | — |
| `silver.dim_country` | `/v2/country` | `country_iso3` | FK region, income_level, lending_type; `is_aggregate` (region = "Aggregates") |
| `silver.dim_source` | `/v2/sources` | `source_id` | `last_updated` (base da carga incremental) |
| `silver.dim_topic` | `/v2/topic` | `topic_id` | — |
| `silver.dim_indicator` | `/v2/indicator/{id}` | `indicator_id` | FK source |
| `silver.bridge_indicator_topic` | campo `topics` do indicador | `(indicator_id, topic_id)` | N:N indicador↔tópico |
| `silver.fact_observation` | `/v2/country/all/indicator/{id}?source=2` | `(country_iso3, indicator_id, period)` | FK country, indicator, source; `year`, `frequency`, `value` (nulo permitido), `unit`, `obs_status`, `decimal`, `ingested_at` |
| `etl.pipeline_run` | controle | `run_id` | pipeline, parâmetros, início/fim, nº registros, status |

Camada gold (materialized views), **um arquivo por view em `sql/gold/`**:
- `sql/gold/country_year_wide.sql` → `gold.country_year_wide` — 1 linha por país/ano com indicadores pivotados + região/renda (só países, sem agregados).
- `sql/gold/income_region_summary.sql` → `gold.income_region_summary` — médias/medianas por nível de renda × região × ano.
- `sql/gold/growth_ranking.sql` → `gold.growth_ranking` — crescimento de PIB e população urbana por país na década, com posição na região.
- `sql/gold/aggregate_reconciliation.sql` → `gold.aggregate_reconciliation` — soma calculada vs. agregado oficial (qualidade).

Cabeçalho obrigatório de cada arquivo:
```sql
-- gold.<nome>
-- Pergunta de negócio: ...
-- Grão (o que é uma linha): ...
-- Origem: silver.fact_observation, silver.dim_country, ...
-- Regras: (cada uma com motivo ou referência a docs/data-decisions.md)
```

### Indicadores iniciais (lista em `configs/*.toml`, validar códigos via `/v2/indicator/{id}` na Fase 2)
`SP.POP.TOTL`, `SP.URB.TOTL.IN.ZS`, `SP.DYN.LE00.IN`, `NY.GDP.MKTP.CD`, `NY.GDP.PCAP.CD`, `NY.GDP.MKTP.KD.ZG`, `FP.CPI.TOTL.ZG`, `SL.UEM.TOTL.ZS`, `SI.POV.DDAY`, `SI.POV.GINI`, `SE.ADT.LITR.ZS`, `SH.XPD.CHEX.GD.ZS`, `EG.ELC.ACCS.ZS`, `IT.NET.USER.ZS`, `EN.GHG.CO2.PC.CE.AR5` (CO₂ per capita; o código antigo `EN.ATM.CO2E.PC` foi descontinuado — confirmar).

## Estrutura alvo

```text
src/world_bank/
├── __main__.py               # CLI (migrate, load-dimensions, load-observations, build-gold, run-all)
├── config.py                 # Settings tipado (pydantic-settings)
├── exceptions.py             # ApiResponseError, SchemaValidationError, LoadError
├── logging_config.py         # configuração única de logging
├── extract/client.py         # WorldBankClient: paginação, retry, detecção de erro no corpo
├── extract/endpoints.py      # fetch_countries, fetch_regions, ..., fetch_observations
├── transform/dimensions.py   # normalize_countries, normalize_regions, ...
├── transform/observations.py # normalize_observations (period → year/frequency, casts)
├── validate/schemas.py       # modelos pydantic dos registros da API
├── validate/checks.py        # colunas, nulos em chaves, unicidade, faixas
├── load/postgres.py          # conexão, insert bronze, upsert silver (COPY+ON CONFLICT), migrate
└── pipelines/{bronze,dimensions,observations,gold}.py
sql/migrations/001_schemas.sql, 002_bronze.sql, 003_silver.sql, 004_etl.sql
sql/gold/country_year_wide.sql, income_region_summary.sql, growth_ranking.sql, aggregate_reconciliation.sql
configs/dev.toml, configs/prod.toml
dashboard/app.py                         # Streamlit
dashboard/powerbi/world_bank.pbix        # Power BI
docs/dashboard/world_bank_powerbi.pdf    # export do Power BI
tests/ (espelha src) + tests/fixtures/*.json
docs/ + mkdocs.yml
docker-compose.yml, .env.example, README.md
```

## Fases de implementação

### Fase 0 — Fundação
- Criar repositório público na conta pessoal do GitHub e configurar `origin`.
- Migrar `main.py` → `src/world_bank/__main__.py`; adicionar `[build-system]` `uv_build` (SKILL §8).
- `uv add httpx tenacity pydantic pydantic-settings pandas "psycopg[binary]"`; `uv add --dev ruff pytest pytest-cov pytest-mock respx mkdocs mkdocs-material`.
- Configs de ruff/pytest/coverage no `pyproject.toml` como no SKILL §4/§5; atualizar `description`.
- `.gitignore` com as entradas do SKILL §8; criar `README.md` (referenciado no `pyproject.toml` e hoje inexistente).
- `docker-compose.yml` (postgres:17, volume nomeado, healthcheck), `.env.example` (`DATABASE_URL=postgresql://wb:wb@localhost:5432/world_bank`, `WB_ENV=dev` — valores fictícios).
- `config.py`, `exceptions.py`, `logging_config.py` + testes; criar `docs/ai-log.md`.

### Fase 1 — Cliente da API (extract)
- `WorldBankClient.get_all(path, params)`: força `format=json` e `per_page` (config, ex. 1000), itera `page=1..pages`, devolve registros + metadados (`lastupdated`).
- Detecta `[{"message": [...]}]` com HTTP 200 → `ApiResponseError` com id/código; registros `None` → lista vazia.
- Retry com backoff exponencial em 5xx, timeout, erros 105/199; timeout configurável.
- Respeitar limites: lotes de até 60 indicadores e URL ≤ 4000 chars (helper de chunking).
- Testes com `respx`: paginação multi-página, página vazia, erro no corpo com 200, retry de 503, timeout.

### Fase 2 — Bronze
- Migrações `001_schemas.sql` e `002_bronze.sql`; comando `migrate`.
- Cada página extraída é gravada **como veio** em `bronze.api_response` (JSONB + endpoint, parâmetros, página, `ingested_at`). Append-only: nada é alterado.
- Conferência: nº de páginas gravadas = `pages` informado pela API; nº de registros no JSON = `total`.

### Fase 3 — Silver: dimensões
- `pipelines/dimensions.py`: lê da bronze → normaliza (casts de `latitude/longitude`, `per_page` string/int, flag `is_aggregate`) → valida → upsert em `silver.dim_*` e `silver.bridge_indicator_topic`.
- Validar os códigos de indicador configurados.
- Testes de transformação puros (sem mocks) com fixtures JSON inventadas.

### Fase 4 — Silver: fato de observações
- `pipelines/observations.py --start 2000 --end 2024`: por indicador, `country/all/indicator/{id}?source=2&date=start:end` → bronze → silver.
- `normalize_observations`: mantém `period` original, deriva `year` e `frequency` (Y/Q/M), mantém `value` nulo, adiciona `ingested_at`.
- Incremental: compara `lastupdated` da fonte com `silver.dim_source`/`etl.pipeline_run`; se não mudou, pula (`--full-refresh` força).
- Upsert pela chave natural → reexecução idempotente; registro em `etl.pipeline_run`.

### Fase 5 — Validação e qualidade
- Pós-extração: estrutura `[metadados, dados]` via pydantic.
- Pré-carga: colunas obrigatórias, chaves sem nulos, unicidade de `(country_iso3, indicator_id, period)`, ano em faixa plausível, valores não negativos onde aplicável (população, PIB), FK de país/indicador existente na dimensão.
- Falha explícita com `SchemaValidationError` e log estruturado; nada passa em silêncio.

### Fase 6 — Gold e CLI
- Pasta `sql/gold/` com um `.sql` por view (cabeçalho obrigatório acima); o schema `gold` é criado em `001_schemas.sql`.
- Comando `build-gold`: aplica cada arquivo de `sql/gold/` em ordem de dependência (`DROP MATERIALIZED VIEW IF EXISTS` + `CREATE MATERIALIZED VIEW`), numa transação; registra em `etl.pipeline_run`.
- Teste unitário (sem banco): todo arquivo de `sql/gold/` tem o cabeçalho completo e cria exatamente a view `gold.<nome do arquivo>`.
- `run-all`: migrate → bronze/dimensões → observações → gold.
- `scripts/backfill.py` opcional para períodos longos.

### Fase 7 — Dashboards (lendo só a camada gold)
- **Streamlit**: `uv add --group dashboard streamlit`; `dashboard/app.py` faz apenas `SELECT ... FROM gold.*` com filtros (região, renda, ano, indicador) aplicados no `WHERE`; nenhum cálculo em pandas/na tela. Rodar com `uv run --group dashboard streamlit run dashboard/app.py`.
- **Power BI Desktop** (gratuito; publicação online exige licença, então não publicamos):
  - Conector PostgreSQL (`localhost:5432`, base `world_bank`), importando **somente** as views `gold.*` — nada de bronze/silver.
  - Sem colunas calculadas nem medidas DAX com regra de negócio: toda métrica já vem pronta da gold. Se faltar um indicador, ele é criado em SQL na gold, não no Power BI.
  - Páginas: visão geral por renda × região; PIB per capita × expectativa de vida; ranking de crescimento; reconciliação de agregados.
  - Versionar `dashboard/powerbi/world_bank.pbix` (sem credenciais salvas) e `docs/dashboard/world_bank_powerbi.pdf` (Arquivo → Exportar → PDF) + prints PNG no README.
- Opcional: GitHub Actions (ruff + pytest com `uv sync --locked`).

### Fase 8 — Documentação e README final
- `mkdocs.yml` e `docs/` conforme SKILL §6; `docs/data-sources.md` incorpora/referencia `doc_api.md`; `docs/architecture.md` com diagrama do medalhão e do modelo estrela; `docs/pipelines.md` com comandos e perguntas de negócio.
- `README.md`: fonte (link + CC BY 4.0), o que é uma linha de cada tabela, as 3 camadas e os indicadores (cada um com link para seu arquivo em `sql/gold/`), como rodar do zero (incluindo testes e dashboards), link para `docs/data-decisions.md`, seção curta "Onde a IA errou" (resumo de `docs/ai-log.md`).

### Commits sugeridos (um por etapa)
1. `chore: estrutura src/, uv, ruff, pytest e docker-compose do Postgres`
2. `feat(extract): cliente da World Bank API com paginação e retry`
3. `feat(bronze): persistência das respostas brutas em bronze.api_response`
4. `feat(silver): dimensões de país, região, renda, fonte, tópico e indicador`
5. `feat(silver): fato de observações com upsert idempotente`
6. `feat(validate): checagens de esquema e qualidade antes da carga`
7. `feat(gold): views de indicadores e comando run-all`
8. `feat(dashboard): painel Streamlit lendo só a camada gold`
9. `feat(dashboard): relatório Power BI (pbix + PDF) sobre a camada gold`
10. `docs: README, MkDocs e registro de erros da IA`

## Arquivos críticos
- `pyproject.toml`, `.gitignore`, `main.py` (remover após migrar), `docker-compose.yml`, `.env.example`, `README.md`
- `src/world_bank/extract/client.py`, `src/world_bank/load/postgres.py`, `sql/migrations/*.sql`, `sql/gold/*.sql`
- `docs/ai-log.md`, `docs/data-decisions.md`
- `src/world_bank/pipelines/*.py`, `tests/conftest.py`, `tests/fixtures/`
- `dashboard/app.py`, `dashboard/powerbi/`, `docs/ai-log.md`

## Verificação (Definition of Done — SKILL §10)
```bash
docker compose up -d
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pytest                          # cobertura >= 70%, sem rede e sem banco
uv run pytest -m integration           # contra o Postgres local
uv run python -m world_bank run-all --start 2000 --end 2024
uv run python -m world_bank run-all --start 2000 --end 2024   # 2ª vez: mesmas contagens na silver (idempotência)
uv run --group dashboard streamlit run dashboard/app.py
uv run mkdocs build --strict
```
Conferência manual: cada view de `gold.*` tem um arquivo em `sql/gold/`; cada regra de dado tem motivo em `docs/data-decisions.md`; `git log --oneline` mostra um commit por fase em ordem; `SELECT count(*)` em cada tabela da silver antes/depois da 2ª execução; bronze só cresce (append-only); `gold.country_year_wide` sem agregados; `gold.aggregate_reconciliation` com diferenças pequenas; Power BI conectado só a `gold.*` e PDF exportado.
