# Dicionário de dados

Colunas de cada tabela, com o tipo de valor e o que significam. Veja também o
[diagrama das ligações](modelagem-silver.svg) e os motivos das decisões em
[data-decisions.md](data-decisions.md).

> Gerado por `scripts/gerar_dicionario.py` a partir do banco. Não edite à mão: para
> mudar uma descrição, altere o `comment on` numa migração e gere de novo.

**Como ler:** *PK* identifica a linha. *FK* aponta para outra tabela. *único* não se
repete. *Vazio?* diz se a coluna aceita ficar sem valor (`NULL`).

## Camada `silver`

Dado limpo, tipado e ligado por chaves. É a camada para consultar.

### `silver.classificacao_renda_anual`

Uma linha = a classificação oficial de renda de um país para um ano (D-038).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | não | PK, FK → `dim_pais.pais_iso3` | País classificado. |
| `ano_referencia` | número inteiro | `smallint` | não | PK | Ano da renda usada na classificação. É o ano para ligar às observações (D-038). |
| `ano_fiscal` | número inteiro | `smallint` | não |  | Ano fiscal do World Bank em que a classificação vigorou. |
| `nivel_renda_id` | texto | `text` | não | FK → `dim_nivel_renda.nivel_renda_id` | Nível de renda do país naquele ano. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_fonte`

Uma linha = uma base de dados do World Bank.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `fonte_id` | número inteiro | `integer` | não | PK | Identificador da fonte (ex.: 2 = WDI). |
| `codigo` | texto | `text` | não | único | Código curto da fonte (ex.: WDI). |
| `nome` | texto | `text` | não |  | Nome da fonte, como veio da API. |
| `conceitos` | número inteiro | `integer` | não |  | Número de conceitos informado pela API. |
| `ultima_atualizacao` | data | `date` | não |  | Data da última atualização da fonte, segundo a API. |
| `tem_dados` | verdadeiro/falso | `boolean` | não |  | A fonte tem dados disponíveis. |
| `tem_metadados` | verdadeiro/falso | `boolean` | sim |  | A fonte tem metadados; NULL quando a API não informa (D-027). |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_indicador`

Uma linha = uma série de dados. Só os indicadores configurados (D-022).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `indicador_id` | texto | `text` | não | PK | Código do indicador (ex.: SP.POP.TOTL). |
| `nome` | texto | `text` | não |  | Nome do indicador, como veio da API. |
| `fonte_id` | número inteiro | `integer` | não | FK → `dim_fonte.fonte_id` | Fonte do indicador. |
| `descricao` | texto | `text` | sim |  | Descrição; NULL se vazia. |
| `organizacao_fonte` | texto | `text` | sim |  | Organização que produz o dado; NULL se vazia. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_nivel_renda`

Uma linha = um nível de renda ou um agrupamento de níveis.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `nivel_renda_id` | texto | `text` | não | PK | Código do nível (ex.: HIC). |
| `nivel_renda_iso2` | texto | `text` | não | único | Código de 2 caracteres da API. |
| `nome` | texto | `text` | não |  | Nome do nível, como veio da API. |
| `ordem` | número inteiro | `smallint` | sim |  | Sequência para ordenar: 1 = baixa, 2 = média-baixa, 3 = média-alta, 4 = alta; NULL nos demais (D-034). |
| `e_agrupamento` | verdadeiro/falso | `boolean` | não |  | true em LMY e MIC, que somam outros níveis: não somar junto com eles (D-034). |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_pais`

Uma linha = um país ou um agregado. Filtre e_agregado para não somar os dois (D-023).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | não | PK | Código de 3 caracteres (campo id da API). |
| `pais_iso2` | texto | `text` | não | único | Código de 2 caracteres; liga as observações sem ISO3 (Fase 4). |
| `nome` | texto | `text` | não |  | Nome do país ou agregado, como veio da API. |
| `regiao_id` | texto | `text` | sim | FK → `dim_regiao.regiao_id` | Região geográfica; NULL em agregados (D-017). |
| `nivel_renda_atual_id` | texto | `text` | sim | FK → `dim_nivel_renda.nivel_renda_id` | Classificação de renda ATUAL, não a de cada ano; NULL em agregados (D-017, D-025). |
| `tipo_emprestimo_atual_id` | texto | `text` | sim | FK → `dim_tipo_emprestimo.tipo_emprestimo_id` | Tipo de empréstimo ATUAL, não o de cada ano; NULL em agregados (D-017, D-025). |
| `regiao_administrativa_id` | texto | `text` | sim | FK → `dim_regiao.regiao_id` | Região sem os países de renda alta; NULL nos demais casos (D-034). |
| `capital` | texto | `text` | sim |  | Capital; NULL se a API não informa. |
| `latitude` | número decimal | `numeric` | sim |  | Latitude; NULL se a API não informa. |
| `longitude` | número decimal | `numeric` | sim |  | Longitude; NULL se a API não informa. |
| `e_agregado` | verdadeiro/falso | `boolean` | não |  | true quando a linha é um agregado, e não um país (D-017). |
| `tipo_agregado` | texto | `text` | sim |  | Em agregados: regiao, renda, tipo_emprestimo ou outro; NULL em países (D-034). |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_regiao`

Uma linha = uma região geográfica ou um agrupamento de países.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `regiao_id` | texto | `text` | não | PK | Código da região (campo code da API, D-016). |
| `regiao_iso2` | texto | `text` | não | único | Código de 2 caracteres da API. |
| `nome` | texto | `text` | não |  | Nome da região, como veio da API. |
| `e_geografica` | verdadeiro/falso | `boolean` | não |  | true nas 7 regiões geográficas; false nos agrupamentos, que se sobrepõem (D-016). |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_tipo_emprestimo`

Uma linha = um tipo de empréstimo do World Bank.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `tipo_emprestimo_id` | texto | `text` | não | PK | Código do tipo (ex.: IBD). |
| `tipo_emprestimo_iso2` | texto | `text` | não | único | Código de 2 caracteres da API. |
| `nome` | texto | `text` | não |  | Nome do tipo, como veio da API. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.dim_topico`

Uma linha = um tema dos indicadores.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `topico_id` | número inteiro | `integer` | não | PK | Identificador do tópico. |
| `nome` | texto | `text` | não |  | Nome do tópico, como veio da API. |
| `descricao` | texto | `text` | sim |  | Descrição do tópico; NULL se vazia. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.fato_observacao`

Uma linha = o valor de um indicador para um país ou agregado em um ano. Filtre dim_pais.e_agregado para não somar os dois (D-040).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | não | PK, FK → `dim_pais.pais_iso3` | País ou agregado medido (D-041). |
| `indicador_id` | texto | `text` | não | PK, FK → `dim_indicador.indicador_id` | Indicador medido. |
| `ano` | número inteiro | `smallint` | não | PK | Ano da observação. |
| `valor` | número decimal | `numeric` | sim |  | Valor medido, sem arredondamento; NULL quando a fonte não tem o dado (D-042, D-043). |
| `casas_decimais` | número inteiro | `smallint` | não |  | Casas sugeridas pela API para exibir o valor; não altera o valor guardado (D-047). |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a linha foi criada ou um valor mudou pela última vez (D-033). |

### `silver.ponte_indicador_topico`

Uma linha = a ligação de um indicador a um tópico (N:N, D-026).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `indicador_id` | texto | `text` | não | PK, FK → `dim_indicador.indicador_id` | Indicador ligado. |
| `topico_id` | número inteiro | `integer` | não | PK, FK → `dim_topico.topico_id` | Tópico ligado. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a ligação foi criada (D-033). |

## Camada `bronze`

Dado como veio da fonte, sem alteração. Serve para auditar.

### `bronze.api_response`

Uma página de resposta da World Bank API v2, como veio. Append-only.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `response_id` | número inteiro | `bigint` | não | PK | Identificador da linha. |
| `run_id` | identificador único | `uuid` | não |  | Execução do pipeline que gravou a página. |
| `endpoint` | texto | `text` | não | único | Caminho chamado na API (ex.: country). |
| `params` | JSON | `jsonb` | não |  | Parâmetros enviados na requisição, sem a página. |
| `params_hash` | texto | `text` | não | único | SHA-256 de endpoint + params (sem page): identifica a requisição (D-012). |
| `page` | número inteiro | `integer` | não | único | Número da página na resposta. |
| `pages` | número inteiro | `integer` | não |  | Total de páginas informado pela API. |
| `total` | número inteiro | `integer` | não |  | Total de registros informado pela API. |
| `record_count` | número inteiro | `integer` | não |  | Registros contados nesta página. |
| `payload` | JSON | `jsonb` | não |  | Resposta da API, sem alteração (D-008). |
| `payload_hash` | texto | `text` | não |  | SHA-256 do payload: detecta se a página mudou desde a última carga (D-010). |
| `ingested_at` | data e hora | `timestamp with time zone` | não | único | Quando a página foi gravada. |

### `bronze.source_file`

Uma linha = uma versão de um arquivo baixado fora da API, como veio. Append-only.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `file_id` | número inteiro | `bigint` | não | PK | Identificador da linha. |
| `run_id` | identificador único | `uuid` | não |  | Execução do pipeline que gravou o arquivo. |
| `source` | texto | `text` | não |  | Identifica o arquivo (ex.: income_history). |
| `url` | texto | `text` | não |  | Endereço de onde o arquivo foi baixado. |
| `content` | arquivo (bytes) | `bytea` | não |  | Bytes do arquivo, sem alteração. |
| `content_hash` | texto | `text` | não |  | SHA-256 do conteúdo: detecta se o arquivo mudou desde a última carga. |
| `size_bytes` | número inteiro | `integer` | não |  | Tamanho do arquivo, em bytes. |
| `ingested_at` | data e hora | `timestamp with time zone` | não |  | Quando o arquivo foi gravado. |

## Camada `etl`

Controle do pipeline.

### `etl.pipeline_run`

Uma linha = uma execução de um comando do pipeline (D-046).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `run_id` | identificador único | `uuid` | não | PK | Identificador da execução. |
| `pipeline` | texto | `text` | não |  | Comando executado (ex.: load-observations). |
| `params` | JSON | `jsonb` | não |  | Período e indicadores usados. |
| `bronze_run_ids` | lista de identificadores | `uuid[]` | não |  | Cargas da bronze lidas, em ordem; vazio se falhou antes de ler (D-045). |
| `status` | texto | `text` | não |  | running, success, skipped ou failed. |
| `rows_read` | número inteiro | `integer` | sim |  | Linhas lidas da bronze. |
| `rows_written` | número inteiro | `integer` | sim |  | Linhas inseridas ou alteradas. |
| `error_message` | texto | `text` | sim |  | Mensagem de erro; só em falha. |
| `started_at` | data e hora | `timestamp with time zone` | não |  | Início da execução. |
| `finished_at` | data e hora | `timestamp with time zone` | sim |  | Fim da execução; NULL enquanto roda. |

### `etl.schema_migrations`

Uma linha = uma migração de sql/migrations/ já aplicada.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `version` | texto | `text` | não | PK | Número da migração (ex.: 003). |
| `filename` | texto | `text` | não |  | Nome do arquivo da migração. |
| `checksum` | texto | `text` | não |  | SHA-256 do arquivo: detecta edição depois de aplicada. |
| `applied_at` | data e hora | `timestamp with time zone` | não |  | Quando a migração foi aplicada. |
