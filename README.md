# World-Bank

[![CI](https://github.com/FranciscoAssislsj/World-Bank/actions/workflows/ci.yml/badge.svg)](https://github.com/FranciscoAssislsj/World-Bank/actions/workflows/ci.yml)

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
uv run python -m world_bank load-dimensions  # grava os cadastros da silver a partir da bronze
uv run python -m world_bank load-observations  # grava os valores dos indicadores na silver
uv run python -m world_bank validate  # inspeciona a qualidade da silver
uv run python -m world_bank build-gold  # recria as views da gold
```

Ou tudo de uma vez, parando na primeira falha. Uma regra de erro impede a gold de ser recriada ([D-068](docs/data-decisions.md)):

```bash
uv run python -m world_bank run-all  # aceita --start, --end e --full-refresh
```

O banco fica na porta **5433** do computador, e não na 5432, para não conflitar com um PostgreSQL já instalado.

`load-bronze` e `load-observations` aceitam `--start` e `--end` para mudar o período das observações (padrão: 2000–2024). Rodar de novo o `load-bronze` só grava as requisições cujo conteúdo mudou na API ([D-010](docs/data-decisions.md)). O `load-observations` é pulado se a bronze não mudou, e `--full-refresh` força o reprocessamento ([D-045](docs/data-decisions.md)).

| Tabela | Uma linha é |
|---|---|
| `bronze.api_response` | uma página de resposta da API, com o JSON original em `payload` |
| `bronze.source_file` | uma versão de um arquivo baixado fora da API, sem alteração |
| `silver.regiao` | uma região geográfica ou um agrupamento de países, já tratado |
| `silver.nivel_renda` | um nível de renda ou um agrupamento de níveis, já tratado |
| `silver.tipo_emprestimo` | um tipo de empréstimo do World Bank, já tratado |
| `silver.pais` | um país ou um agregado, já tratado |
| `silver.classificacao_renda_anual` | a classificação oficial de renda de um país em um ano |
| `silver.fonte` | uma base de dados do World Bank, já tratada |
| `silver.topico` | um tema dos indicadores, já tratado |
| `silver.indicador` | uma série de dados, já tratada |
| `silver.indicador_topico` | a ligação entre um indicador e um tema |
| `silver.observacao` | o valor de um indicador para um país ou agregado em um ano, já tratado |
| `silver.nome_portugues` | o nome em português de um código da API ([D-082](docs/data-decisions.md)) |
| [`gold.dim_regiao`](sql/gold/01_dim_regiao.sql) | uma região ou um agrupamento de países |
| [`gold.dim_nivel_renda`](sql/gold/02_dim_nivel_renda.sql) | um nível de renda ou um agrupamento de níveis |
| [`gold.dim_tipo_emprestimo`](sql/gold/03_dim_tipo_emprestimo.sql) | um tipo de empréstimo |
| [`gold.dim_fonte`](sql/gold/04_dim_fonte.sql) | uma base de dados do World Bank |
| [`gold.dim_topico`](sql/gold/05_dim_topico.sql) | um tema dos indicadores |
| [`gold.dim_pais`](sql/gold/06_dim_pais.sql) | um país ou um agregado |
| [`gold.dim_indicador`](sql/gold/07_dim_indicador.sql) | uma série de dados |
| [`gold.ponte_indicador_topico`](sql/gold/08_ponte_indicador_topico.sql) | a ligação entre um indicador e um tema |
| [`gold.fato_observacao`](sql/gold/09_fato_observacao.sql) | o valor de um indicador para um país ou agregado em um ano |
| [`gold.fato_renda_anual`](sql/gold/10_fato_renda_anual.sql) | a classificação oficial de renda de um país em um ano |
| [`gold.valores_atipicos`](sql/gold/11_valores_atipicos.sql) | um valor apontado como estranho, com o motivo e o tratamento |
| [`gold.pais_ano`](sql/gold/20_pais_ano.sql) | um país em um ano, com um indicador por coluna |
| [`gold.resumo_renda_regiao`](sql/gold/21_resumo_renda_regiao.sql) | um indicador em um ano, em um recorte de renda, região ou mundo; filtre `recorte` para não contar em dobro |
| [`gold.resumo_anual`](sql/gold/22_resumo_anual.sql) | um ano, com os números dos cartões dos dashboards |
| [`gold.ranking_crescimento`](sql/gold/23_ranking_crescimento.sql) | um país, com o crescimento na última década e a posição |
| [`gold.reconciliacao_agregados`](sql/gold/24_reconciliacao_agregados.sql) | a soma dos países contra o número oficial, por agregado, indicador e ano |
| `etl.pipeline_run` | uma execução de um comando do pipeline |
| `etl.quality_check` | o resultado de uma regra de qualidade em uma execução |
| `etl.schema_migrations` | uma migração de `sql/migrations/` já aplicada |

## Modelo de dados

![Modelo estrela da gold: fato_observacao liga dim_pais e dim_indicador; fato_renda_anual liga dim_pais e dim_nivel_renda; dim_pais liga-se a dim_regiao, dim_nivel_renda e dim_tipo_emprestimo; dim_indicador liga-se a dim_fonte e, pela ponte_indicador_topico, a dim_topico](docs/modelagem-gold.svg)

Cada camada tem um papel ([D-087](docs/data-decisions.md)): a **bronze** guarda o dado como veio, a **silver** trata (tipos, chaves e duplicatas), e a **gold** publica o modelo estrela e as tabelas prontas para os dashboards. As tabelas de consumo leem só a estrela da gold.

`fato_observacao` guarda os valores e liga países e indicadores. Ao somar, filtre `dim_pais.e_agregado`, para não contar países e agregados juntos. Para a renda de um país em um ano, use `fato_renda_anual`.

As colunas de cada tabela, com tipo de valor e descrição, estão no [dicionário de dados](docs/dicionario-dados.md).

## Qualidade dos dados

Cada regra é um arquivo em `sql/quality/`. **Erro** é o que não pode ser verdade, como um percentual acima de 100: a carga é desfeita e nada é publicado. **Aviso** é o que pode ser real e merece atenção: fica registrado em `etl.quality_check`.

Os valores da fonte nunca são alterados, e o dado do World Bank é tratado como fiel ([D-052 e D-070](docs/data-decisions.md)). Ao usar os dados, considere os avisos atuais:

- **Valores improváveis (29):** cada caso foi investigado, e todos ficam nas contas, com o número da fonte e uma marca ([D-062](docs/data-decisions.md)). A média de um grupo pequeno pode ser puxada por um deles: em 2012, o CO₂ per capita de Palau leva a média do seu grupo de 9 países a 24,90, com mediana de 1,32. Por isso, `gold.resumo_renda_regiao` traz `mediana` e `valores_atipicos` ao lado de `media`. A lista está em `gold.valores_atipicos`, e a investigação, em [data-decisions.md](docs/data-decisions.md).
- **Pouca cobertura (76 pares de indicador e ano):** alfabetização, pobreza, Gini e gastos com saúde têm valor em menos da metade dos países em alguns anos, inclusive em 2024.
- **Sem classificação de renda (129 pares de país e ano).**
- **Agregado sem nenhum valor (1):** `Not classified`.

## Testes e qualidade

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest                # testes unitários: sem rede e sem banco, cobertura >= 70%
uv run --group dashboard pytest -m integration --no-cov # testes contra o PostgreSQL local, com a silver carregada
```

O `--no-cov` existe porque a cobertura mínima vale para os testes unitários. Sem ele, o comando termina com erro mesmo com todos os testes passando.

Para conferir cada commit na sua máquina, ative o [pre-commit](.pre-commit-config.yaml) uma vez, depois do `uv sync`:

```bash
uv run pre-commit install
uv run pre-commit run --all-files   # opcional: confere o projeto inteiro agora
```

Ele roda o Ruff, confere o `uv.lock` e barra arquivo `.env`, chave privada e arquivo grande ([D-075](docs/data-decisions.md)). Se ele corrigir um arquivo, o commit para: rode `git add` nesse arquivo e faça o commit de novo.

O [CI](.github/workflows/ci.yml) roda essas conferências em uma máquina limpa a cada envio para `dev` e `main` e em cada pull request para a `main`. Ele sobe o banco, roda o `run-all` contra a API real e não aceita teste de integração pulado ([D-071 a D-074](docs/data-decisions.md)). Se a API do World Bank estiver fora do ar, o CI fica vermelho sem que o código tenha problema: nesse caso, rode de novo.

## Dashboards

O layout foi desenhado antes, no Figma ([imagens](docs/dashboard/layout/)), e as telas atuais estão em [docs/dashboard/streamlit](docs/dashboard/streamlit/). Os dashboards leem só a gold, com um usuário do banco que não consegue ler mais nada ([D-078 e D-079](docs/data-decisions.md)).

```bash
uv run python -m world_bank migrate   # define a senha do usuário dos dashboards, vinda do .env
uv run --group dashboard streamlit run dashboard/app.py   # abre em http://localhost:8501
```

| Tela | O que mostra |
|---|---|
| Renda e qualidade de vida | Países analisados, expectativa de vida por faixa de renda e PIB per capita × expectativa de vida |
| PIB e crescimento | PIB por país ao longo do tempo, os 10 maiores PIBs e o ranking de crescimento dos últimos 10 anos |

### Power BI

O relatório está em [`dashboard/powerbi/`](dashboard/powerbi/), como projeto `.pbip`: texto que o git consegue comparar ([D-086](docs/data-decisions.md)). Ele não guarda dados nem senha.

1. Com o banco ligado, abra `dashboard/powerbi/world_bank.pbip` no Power BI Desktop.
2. Clique em **Atualizar** e aprove as consultas ao banco.
3. Na credencial do banco, escolha **Banco de dados**, com o usuário `dashboard_leitor` e a senha de `DASHBOARD_DATABASE_URL`. Se o programa avisar sobre conexão sem criptografia, aceite: o banco só existe na sua máquina.

Para mudar o endereço do banco, altere os parâmetros `ServidorBanco` e `NomeBanco`, em **Transformar dados**. As imagens das telas estão em [docs/dashboard/powerbi/](docs/dashboard/powerbi/), e o relatório exportado em [PDF](docs/dashboard/world_bank_powerbi.pdf). O PDF mostra as primeiras linhas do ranking; a lista completa está no relatório.

## Consultar o banco pelo Claude Code (opcional)

O `docker-compose.yml` traz uma ponte [MCP](https://modelcontextprotocol.io) só de leitura, usada por todas as sessões ([D-076](docs/data-decisions.md)). Para ativar, tire o `#` da linha `COMPOSE_PROFILES=mcp` no `.env`, rode `docker compose up -d --wait` e crie o `.mcp.json` na raiz do projeto, que não é versionado:

```json
{
  "mcpServers": {
    "postgres": { "type": "sse", "url": "http://127.0.0.1:8000/sse" }
  }
}
```
