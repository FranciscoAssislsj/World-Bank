# World Bank Indicators API (v2): resumo

Resumo da documentação oficial ([Developer Information](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589-developer-information)), com foco no uso em um pipeline de engenharia de dados.

---

## 1. Visão geral

- Acesso programático a **~16 mil séries temporais**, as mesmas do DataBank e do Open Data.
- Cobre **mais de 45 bases**, como World Development Indicators (WDI), International Debt Statistics, Doing Business, Human Capital Index e Subnational Poverty.
- **Somente a v2 está ativa.** A v1 foi aposentada, e chamadas a ela retornam "Resource not found".
- **Sem autenticação**: não precisa de API key.
- **URL base:** `https://api.worldbank.org/v2`

```
https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL
```

---

## 2. Estrutura das chamadas

Há duas formas equivalentes de filtrar:

| Forma | Exemplo |
|---|---|
| Por argumento (query string) | `/v2/country?incomeLevel=LIC` |
| Por path (segmentos da URL) | `/v2/incomeLevel/LIC/country` |

Padrão para dados: `/v2/country/{países}/indicator/{indicadores}?{parâmetros}`

**Delimitadores**

| Símbolo | Significado | Exemplo |
|---|---|---|
| `;` | vários valores (países, indicadores, fontes) | `country/chn;bra` |
| `:` | intervalo (datas ou números) | `date=2000:2010` |

**Idioma:** vai no path logo depois de `/v2/`, por exemplo `/v2/pt/country/br`. Os idiomas gerais são `en` (padrão), `es`, `fr`, `ar` e `zh`, e há outros locais, como `pt`, `de` e `ja`. A lista completa sai de `/v2/languages`. Nem todo nome está traduzido.

---

## 3. Parâmetros de query

| Parâmetro | Valores | Observação |
|---|---|---|
| `format` | `xml` (padrão), `json`, `jsonP`, `jsonstat` | `jsonP` exige `prefix=NomeCallback` |
| `page` | inteiro | página a retornar |
| `per_page` | inteiro (padrão **50**) | registros por página |
| `date` | `2000`, `2012M01`, `2013Q1`, `2000:2010`, `2012M01:2012M08`, `YTD:2013` | ano, mês, trimestre, intervalo ou acumulado no ano |
| `mrv` | N | N valores mais recentes |
| `mrnev` | N | N valores mais recentes **não vazios** |
| `gapfill` | `Y` / `N` | usado com `mrv`: preenche lacunas com o último valor disponível |
| `frequency` | `Y`, `Q`, `M` | usado com `mrv`: anual, trimestral ou mensal |
| `source` | ID da fonte (ex. `2` = WDI) | obrigatório ao pedir **vários indicadores** |
| `footnote` | `y` | inclui notas de rodapé por país/indicador/ano |
| `downloadformat` | `csv`, `xml`, `excel` | usado com `source`; devolve um **ZIP** |

Exemplos:

```
/v2/country/all/indicator/SP.POP.TOTL?format=json&date=2000:2020&per_page=1000
/v2/country/chn;ago/indicator/SI.POV.DDAY?mrnev=5&format=json
/v2/country/chn;ago/indicator/SI.POV.DDAY;SP.POP.TOTL?source=2&date=2000:2010
/v2/country/ind/indicator/SI.POV.DDAY?source=2&downloadformat=csv
```

---

## 4. Endpoints principais

### Dimensões / cadastros

| Recurso | Endpoint | Exemplo |
|---|---|---|
| Países | `/v2/country` | `/v2/country/br?format=json` |
| Regiões | `/v2/region` | `/v2/region/LCN` |
| Países de uma região | `/v2/country?region={cod}` | `/v2/country?region=LCN` |
| Níveis de renda | `/v2/incomelevel` | `/v2/incomelevel/UMC` |
| Países por renda | `/v2/country?incomelevel={cod}` | `/v2/country?incomelevel=UMC` |
| Tipos de empréstimo | `/v2/lendingtypes` | `/v2/lendingtype/IBD;IDB` |
| Indicadores | `/v2/indicator` | `/v2/indicator/NY.GDP.MKTP.CD` |
| Tópicos | `/v2/topic` | `/v2/topic/5;11` |
| Indicadores de um tópico | `/v2/topic/{id}/indicator` | `/v2/indicator?topic=5` |
| Fontes (bases) | `/v2/sources` | `/v2/sources/2` |
| Idiomas | `/v2/languages` | — |

### Dados (observações)

```
/v2/country/{países}/indicator/{indicador}
/v2/country/br/indicator/NY.GDP.MKTP.CD?date=2006&format=json
/v2/source/11/indicator/NY.GDP.MKTP.CD          # indicador presente em várias fontes
/v2/country/LCN/indicator/NY.GDP.MKTP.CD        # agregado: código da região no lugar do país
```

> Um indicador que existe em mais de uma fonte precisa de `source` explícito.

---

## 5. Formato da resposta (JSON)

A resposta é um **array de 2 posições**: `[metadados, dados]`.

```json
[
  {
    "page": 1, "pages": 1, "per_page": 50, "total": 4,
    "sourceid": "2", "lastupdated": "2026-10-08"
  },
  [
    {
      "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
      "country":   {"id": "BR", "value": "Brazil"},
      "countryiso3code": "BRA",
      "date": "2021",
      "value": 1670647398904.9,
      "unit": "",
      "obs_status": "",
      "decimal": 0
    }
  ]
]
```

**Metadados de paginação:** `page`, `pages`, `per_page`, `total` e, nos dados, `sourceid` e `lastupdated`.

**Campos de um país** (`/v2/country`):

| Campo | Conteúdo |
|---|---|
| `id` | ISO 3166-1 alfa-3 (ex. `BRA`); se não existir, código do Banco Mundial (ex. `CHI`) |
| `iso2Code` | ISO alfa-2 (ex. `BR`) |
| `name` | nome |
| `region`, `adminregion` | `{id, iso2code, value}` |
| `incomeLevel` | `{id, iso2code, value}` |
| `lendingType` | `{id, iso2code, value}` |
| `capitalCity`, `longitude`, `latitude` | capital e coordenadas |

**Campos de um indicador:** `id`, `name`, `unit`, `source`, `sourceNote`, `sourceOrganization` e `topics`.

---

## 6. API avançada e de metadados

### Consultas por fonte, conceito e variável

| Tipo | Exemplo |
|---|---|
| Conceitos (dimensões) de uma fonte | `/v2/sources/2/concepts/data` |
| Variáveis de um conceito | `/v2/sources/2/country/data` |
| Variável específica | `/v2/sources/57/country/ALB/data` |
| Multidimensional | `/v2/sources/57/country/ALB/series/SP.POP.TOTL/time/all/version/199704/data?format=json` |

As palavras-chave das dimensões são `country`, `series`, `time` e `version`. O formato `jsonstat` está em beta.

### Metadados

| Tipo | Exemplo |
|---|---|
| Conceitos com metadados | `/v2/sources/2/concepts/metadata` |
| Tipos de metadados | `/v2/sources/2/metatypes` |
| Metadados de país/série | `/v2/sources/2/country/usa;jpn/series/SP.POP.TOTL/metadata` |
| Busca por palavra-chave | `/v2/sources/2/search/solid%20fuel` |
| Exportação | `...metadata?downloadformat=csv` (ou `excel`) |

---

## 7. Limites

- No máximo **60 indicadores** por requisição.
- No máximo **1.500 caracteres** entre duas barras do path.
- No máximo **4.000 caracteres** na URL inteira.
- **Não há ordenação**: os resultados vêm em ordem aproximadamente alfabética.
- Pedir vários indicadores exige `source`.
- A documentação não publica limite de taxa (rate limit), mas convém limitar a concorrência.

---

## 8. Códigos de erro

| Código | HTTP | Mensagem |
|---|---|---|
| 105 | 503 | Service currently unavailable |
| 110 | 404 | API Version "XXX" not found |
| 111 | 404 | Format "XXX" not found |
| 112 | 404 | Method "XXX" not found |
| 115 | 404 | Missing required parameter |
| 120 | 404 | Parameter "XXX" has an invalid value |
| 140 | 400 | Endpoint "XXX" not found |
| 150 | 400 | Language "XX" is not yet supported |
| 160 | 400 | Filtering by indicator value without a date range |
| 199 | 500 | Unexpected error |

O erro vem **no corpo da resposta**: `wb:error` no XML ou `[{"message": [{"id", "key", "value"}]}]` no JSON. **Na prática, a API pode devolver HTTP 200 mesmo com erro** (testado: indicador inválido retorna 200 com `id: "120"`). Por isso, valide o conteúdo e não apenas o status HTTP.

---

## 9. Boas práticas oficiais

- **Use JSON**, que é menor que XML.
- **Faça cache**: os dados mudam pouco, e só a primeira chamada é lenta.
- **Trate indisponibilidade**: não há garantia de 100% de uptime, então a falha deve ser controlada.
- **Prefira intervalos** (`date=2000:2020`) a várias chamadas de um ano cada.

---

## 10. Implicações para engenharia de dados

- **Paginação:** leia `pages` na primeira resposta e itere `page=1..pages`. Use `per_page` alto (ex. 1000) para reduzir o número de chamadas.
- **Carga incremental:** use `lastupdated` da fonte para decidir se recarrega, e `mrv`/`mrnev` para trazer só os períodos recentes.
- **Resiliência:** retry com backoff exponencial para 503/105 e 500/199, timeout explícito e validação do corpo (array de 2 posições, sem `message`).
- **Valores nulos:** `value: null` é muito comum. Mantenha os nulos na camada bruta e decida o tratamento depois.
- **Agregados misturados:** `country/all` inclui regiões e grupos de renda junto com os países. Filtre pelo cadastro de países (`region.id != "NA"`, já que agregados têm região "Aggregates").
- **Modelagem sugerida:**
  - Dimensões: `country`, `region`, `income_level`, `lending_type`, `indicator`, `topic`, `source`.
  - Fato: `observation (country_iso3, indicator_id, date, value, unit, obs_status, decimal, source_id, ingested_at)`.
- **Tipos inconsistentes:** `per_page` às vezes vem como string (`"50"`) e às vezes como número, e `latitude`/`longitude` vêm como string (vazia nos agregados). Faça cast explícito.
- **Datas heterogêneas:** `date` pode ser `2020`, `2020Q1` ou `2020M01`, então guarde o texto original e uma coluna de frequência.
- **Carga em massa:** para cargas iniciais grandes, `downloadformat=csv` com `source` devolve um ZIP e pode ser mais eficiente que paginar.

---

## 11. Referências

- [About the Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation)
- [API Basic Call Structures](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures)
- [Country API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898590-country-api-queries)
- [Aggregate API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898614-aggregate-api-queries)
- [Indicator API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898599-indicator-api-queries)
- [Topic API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898611-topic-api-queries)
- [Advanced Data API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886686-advanced-data-api-queries)
- [Metadata API Queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/1886695-metadata-api-queries)
- [API Error Codes](https://datahelpdesk.worldbank.org/knowledgebase/articles/898620-api-error-codes)
- [Development Best Practices](https://datahelpdesk.worldbank.org/knowledgebase/articles/902064-development-best-practices)
