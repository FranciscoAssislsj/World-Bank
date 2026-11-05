# Dicionário de dados

Colunas de cada tabela, com o tipo de valor e o que significam. Veja também o
[diagrama das ligações](modelagem-silver.svg) e os motivos das decisões em
[data-decisions.md](data-decisions.md).

> Gerado por `scripts/gerar_dicionario.py` a partir do banco. Não edite à mão: para
> mudar uma descrição, altere o `comment on` numa migração, ou o cabeçalho do arquivo
> em `sql/gold/`, e gere de novo.

**Como ler:** *PK* identifica a linha. *FK* aponta para outra tabela. *único* não se
repete. *Vazio?* diz se a coluna aceita ficar sem valor (`NULL`).

## Camada `gold`

Indicadores prontos para os dashboards. Cada view vem de um arquivo em `sql/gold/`.

### `gold.pais_ano`

Como PIB per capita, expectativa de vida, eletricidade e internet se relacionam em cada país e ano? Uma linha = um país em um ano, com um indicador por coluna.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | sim |  | Código ISO3 do país. |
| `pais` | texto | `text` | sim |  | Nome do país. |
| `ano` | número inteiro | `smallint` | sim |  | Ano da observação. |
| `regiao_id` | texto | `text` | sim |  | Código da região geográfica atual; a fonte não tem histórico. |
| `regiao` | texto | `text` | sim |  | Nome da região. |
| `nivel_renda_id` | texto | `text` | sim |  | Nível de renda naquele ano; NULL se o país não foi classificado (D-059). |
| `nivel_renda` | texto | `text` | sim |  | Nome do nível de renda naquele ano. |
| `nivel_renda_ordem` | número inteiro | `smallint` | sim |  | Ordem do nível, do menor para o maior, para ordenar gráficos. |
| `populacao` | número decimal | `numeric` | sim |  | População total (SP.POP.TOTL). |
| `populacao_urbana_pct` | número decimal | `numeric` | sim |  | População urbana, em % do total (SP.URB.TOTL.IN.ZS). |
| `expectativa_vida` | número decimal | `numeric` | sim |  | Expectativa de vida ao nascer, em anos (SP.DYN.LE00.IN). |
| `pib_usd` | número decimal | `numeric` | sim |  | PIB em dólares correntes (NY.GDP.MKTP.CD). |
| `pib_per_capita_usd` | número decimal | `numeric` | sim |  | PIB per capita em dólares correntes (NY.GDP.PCAP.CD). |
| `crescimento_pib_pct` | número decimal | `numeric` | sim |  | Crescimento real do PIB no ano, em % (NY.GDP.MKTP.KD.ZG). |
| `inflacao_pct` | número decimal | `numeric` | sim |  | Inflação ao consumidor no ano, em % (FP.CPI.TOTL.ZG). |
| `desemprego_pct` | número decimal | `numeric` | sim |  | Desemprego, em % da força de trabalho (SL.UEM.TOTL.ZS). |
| `pobreza_pct` | número decimal | `numeric` | sim |  | População abaixo da linha de US$ 3,00 por dia, em % (SI.POV.DDAY). |
| `gini` | número decimal | `numeric` | sim |  | Índice de Gini (SI.POV.GINI). |
| `alfabetizacao_pct` | número decimal | `numeric` | sim |  | Alfabetização de adultos, em % (SE.ADT.LITR.ZS). |
| `gasto_saude_pib_pct` | número decimal | `numeric` | sim |  | Gasto corrente em saúde, em % do PIB (SH.XPD.CHEX.GD.ZS). |
| `acesso_eletricidade_pct` | número decimal | `numeric` | sim |  | Acesso à eletricidade, em % da população (EG.ELC.ACCS.ZS). |
| `acesso_internet_pct` | número decimal | `numeric` | sim |  | Pessoas que usam internet, em % da população (IT.NET.USER.ZS). |
| `co2_per_capita` | número decimal | `numeric` | sim |  | CO2 por pessoa, em toneladas de CO2 equivalente (EN.GHG.CO2.PC.CE.AR5). |
| `tem_valor_atipico` | verdadeiro/falso | `boolean` | sim |  | true quando algum valor desta linha foi apontado como estranho; o motivo diz qual (D-062). |
| `motivo_atipico` | texto | `text` | sim |  | Qual valor foi apontado e por quê; NULL se nenhum foi (D-062). |

### `gold.ranking_crescimento`

Quais países mais cresceram na última década, em PIB real e em população urbana, por região? Uma linha = um país, na janela dos últimos 10 anos com dado.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | sim |  | Código ISO3 do país. |
| `pais` | texto | `text` | sim |  | Nome do país. |
| `regiao_id` | texto | `text` | sim |  | Código da região geográfica atual. |
| `regiao` | texto | `text` | sim |  | Nome da região. |
| `nivel_renda_atual_id` | texto | `text` | sim |  | Nível de renda atual; não é o de cada ano da janela (D-025). |
| `nivel_renda_atual` | texto | `text` | sim |  | Nome do nível de renda atual. |
| `ano_inicial` | número inteiro | `integer` | sim |  | Ano-base da janela: 10 anos antes de ano_final. |
| `ano_final` | número inteiro | `smallint` | sim |  | Último ano com crescimento do PIB no fato (D-064). |
| `crescimento_pib_real_pct` | número decimal | `numeric` | sim |  | Crescimento real do PIB na janela, em %; NULL se faltar um ano (D-064). |
| `posicao_pib_regiao` | número inteiro | `bigint` | sim |  | Posição na região, do maior para o menor crescimento; NULL sem crescimento. |
| `posicao_pib_mundo` | número inteiro | `bigint` | sim |  | Posição no mundo, do maior para o menor crescimento; NULL sem crescimento. |
| `populacao_urbana_inicial` | número decimal | `numeric` | sim |  | População urbana em ano_inicial (D-065). |
| `populacao_urbana_final` | número decimal | `numeric` | sim |  | População urbana em ano_final (D-065). |
| `crescimento_populacao_urbana_pct` | número decimal | `numeric` | sim |  | Variação da população urbana na janela, em %. |
| `posicao_populacao_urbana_regiao` | número inteiro | `bigint` | sim |  | Posição na região; NULL sem crescimento. |
| `posicao_populacao_urbana_mundo` | número inteiro | `bigint` | sim |  | Posição no mundo; NULL sem crescimento. |

### `gold.reconciliacao_agregados`

A soma dos países bate com o número oficial do World Bank? Uma linha = um agregado (região, nível de renda ou mundo), um indicador somável e um ano.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `agregado_id` | texto | `text` | sim |  | Código do agregado na API. |
| `agregado` | texto | `text` | sim |  | Nome do agregado em português (D-082). |
| `tipo` | texto | `text` | sim |  | regiao, renda ou mundo. |
| `indicador_id` | texto | `text` | sim |  | Código do indicador. |
| `indicador` | texto | `text` | sim |  | Nome do indicador em português (D-082). |
| `ano` | número inteiro | `smallint` | sim |  | Ano da observação. |
| `soma_paises` | número decimal | `numeric` | sim |  | Soma calculada a partir dos países. |
| `valor_oficial` | número decimal | `numeric` | sim |  | Valor do agregado publicado pela API. |
| `diferenca` | número decimal | `numeric` | sim |  | soma_paises menos valor_oficial. |
| `diferenca_pct` | número decimal | `numeric` | sim |  | A diferença, em % do valor oficial. |
| `paises_sem_valor` | número inteiro | `bigint` | sim |  | Países do grupo sem dado; explica boa parte da diferença no PIB (D-066). |
| `dentro_da_tolerancia` | verdadeiro/falso | `boolean` | sim |  | true quando a diferença é de até 2%; false também se faltar o oficial (D-066). |

### `gold.resumo_renda_regiao`

Como cada indicador evolui por nível de renda e por região, incluindo pobreza e desigualdade? Uma linha = um indicador em um ano, em um recorte (renda_regiao, renda, regiao ou mundo).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `recorte` | texto | `text` | sim |  | renda_regiao, renda, regiao ou mundo (D-060). |
| `ano` | número inteiro | `smallint` | sim |  | Ano da observação. |
| `indicador_id` | texto | `text` | sim |  | Código do indicador. |
| `indicador` | texto | `text` | sim |  | Nome do indicador em português (D-082). |
| `nivel_renda_id` | texto | `text` | sim |  | Nível de renda naquele ano; NULL se o recorte não usa renda. |
| `nivel_renda` | texto | `text` | sim |  | Nome do nível de renda. |
| `nivel_renda_ordem` | número inteiro | `smallint` | sim |  | Ordem do nível, do menor para o maior, para ordenar gráficos. |
| `regiao_id` | texto | `text` | sim |  | Código da região; NULL se o recorte não usa região. |
| `regiao` | texto | `text` | sim |  | Nome da região. |
| `media` | número decimal | `numeric` | sim |  | Média simples com todos os valores da silver; cada país pesa igual (D-061). |
| `mediana` | número decimal | `numeric` | sim |  | Mediana com todos os valores da silver; quase não muda com um valor extremo (D-061). |
| `paises_com_valor` | número inteiro | `bigint` | sim |  | Quantos países têm valor (D-063). |
| `paises_no_grupo` | número inteiro | `bigint` | sim |  | Quantos países o grupo tem naquele ano (D-063). |
| `cobertura_pct` | número decimal | `numeric` | sim |  | Países com valor, em % do grupo (D-063). |
| `cobertura_baixa` | verdadeiro/falso | `boolean` | sim |  | true quando menos de 50% dos países têm valor (D-063). |
| `valores_atipicos` | número inteiro | `bigint` | sim |  | Quantos valores deste grupo foram apontados como estranhos; todos entram nas contas (D-062). |
| `casas_decimais` | número inteiro | `smallint` | sim |  | Casas sugeridas pela API para exibir o valor (D-047). |

### `gold.valores_atipicos`

Quais valores foram apontados como estranhos, e o que foi feito com cada um? Uma linha = um valor apontado, de um país, um indicador e um ano.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | sim |  | Código ISO3 do país. |
| `pais` | texto | `text` | sim |  | Nome do país. |
| `indicador_id` | texto | `text` | sim |  | Código do indicador. |
| `indicador` | texto | `text` | sim |  | Nome do indicador em português (D-082). |
| `ano` | número inteiro | `smallint` | sim |  | Ano do valor. |
| `valor_original` | número decimal | `numeric` | sim |  | O valor como está na silver. |
| `motivo` | texto | `text` | sim |  | O limite que o valor ultrapassou. |
| `tratamento` | texto | `text` | sim |  | O que foi feito com o valor, em uma frase. |

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

### `silver.nome_portugues`

Nome em português de cada país, região, faixa de renda, indicador e agregado.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `categoria` | texto | `text` | não | PK | pais, regiao, renda, indicador ou agregado. |
| `codigo` | texto | `text` | não | PK | O código usado pela API. |
| `nome` | texto | `text` | não |  | O nome mostrado nos dashboards. |

### `silver.ponte_indicador_topico`

Uma linha = a ligação de um indicador a um tópico (N:N, D-026).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `indicador_id` | texto | `text` | não | PK, FK → `dim_indicador.indicador_id` | Indicador ligado. |
| `topico_id` | número inteiro | `integer` | não | PK, FK → `dim_topico.topico_id` | Tópico ligado. |
| `bronze_run_id` | identificador único | `uuid` | não |  | Carga da bronze de onde a linha veio (D-033). |
| `atualizado_em` | data e hora | `timestamp with time zone` | não |  | Quando a ligação foi criada (D-033). |

### `silver.valor_atipico`

Uma linha = um valor apontado como estranho, com o motivo e o tratamento (D-062).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `pais_iso3` | texto | `text` | sim |  | País ou agregado do valor. |
| `indicador_id` | texto | `text` | sim |  | Indicador do valor. |
| `ano` | número inteiro | `smallint` | sim |  | Ano do valor. |
| `valor` | número decimal | `numeric` | sim |  | O valor como está em fato_observacao. |
| `motivo` | texto | `text` | sim |  | O limite que o valor ultrapassou. |
| `tratamento` | texto | `text` | sim |  | O que é feito com o valor, em uma frase. |

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

### `etl.quality_check`

Uma linha = o resultado de uma regra de qualidade em uma execução (D-054).

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `check_id` | número inteiro | `bigint` | não | PK | Identificador da linha. |
| `run_id` | identificador único | `uuid` | não | FK → `pipeline_run.run_id` | Execução que rodou a regra. |
| `check_name` | texto | `text` | não |  | Nome do arquivo em sql/quality/, sem .sql. |
| `severity` | texto | `text` | não |  | error bloqueia; warning só registra (D-051). |
| `passed` | verdadeiro/falso | `boolean` | não |  | true quando não há linhas com problema. |
| `rows_failed` | número inteiro | `integer` | não |  | Linhas com problema. |
| `sample` | JSON | `jsonb` | não |  | Até 5 exemplos das linhas com problema. |
| `checked_at` | data e hora | `timestamp with time zone` | não |  | Quando o resultado foi gravado. |

### `etl.schema_migrations`

Uma linha = uma migração de sql/migrations/ já aplicada.

| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |
|---|---|---|---|---|---|
| `version` | texto | `text` | não | PK | Número da migração (ex.: 003). |
| `filename` | texto | `text` | não |  | Nome do arquivo da migração. |
| `checksum` | texto | `text` | não |  | SHA-256 do arquivo: detecta edição depois de aplicada. |
| `applied_at` | data e hora | `timestamp with time zone` | não |  | Quando a migração foi aplicada. |
