# Fontes de dados

O projeto usa duas fontes do World Bank, ambas sob licença [CC BY 4.0](https://datacatalog.worldbank.org/public-licenses#cc-by):

- **World Bank Indicators API v2:** países, cadastros e valores dos indicadores.
- **Arquivo `OGHIST`:** histórico oficial da classificação de renda, porque a API só informa a renda atual ([D-036 e D-037](data-decisions.md)).

Esta página resume a [documentação oficial](https://datahelpdesk.worldbank.org/knowledgebase/topics/125589-developer-information), com foco no uso em um pipeline.

## Visão geral da API

- Dá acesso a **cerca de 16 mil séries temporais**, de **mais de 45 bases**, como a World Development Indicators (WDI).
- **Só a v2 está ativa.** Chamadas à v1 retornam "Resource not found".
- **Não pede autenticação.**
- **URL base:** `https://api.worldbank.org/v2`

```text
https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL
```

## Como este projeto usa a API

| Dado | Endpoint | Destino na bronze |
|---|---|---|
| Regiões | `/region` | `bronze.api_response` |
| Níveis de renda | `/incomelevel` | `bronze.api_response` |
| Tipos de empréstimo | `/lendingtypes` | `bronze.api_response` |
| Países e agregados | `/country` | `bronze.api_response` |
| Bases de dados | `/sources` | `bronze.api_response` |
| Temas | `/topic` | `bronze.api_response` |
| Cadastro de cada indicador | `/indicator/{id}` | `bronze.api_response` |
| Valores | `/country/all/indicator/{ids}?date=2000:2024&source=2` | `bronze.api_response` |

| Comportamento da API | O que o projeto faz |
|---|---|
| Os dados vêm em páginas | lê `pages` e busca todas, com 1.000 registros por página |
| A API pode ficar fora do ar | repete com espera crescente em timeout, falha de rede e erros temporários |
| Pode responder HTTP 200 com erro no corpo | confere o conteúdo, e não só o status |
| `value: null` é muito comum | mantém o vazio, sem preencher ([D-042](data-decisions.md)) |
| `country/all` mistura países e agregados | separa os dois com `e_agregado` ([D-023](data-decisions.md)) |
| Os dados mudam pouco | compara o conteúdo e só grava o que mudou ([D-010](data-decisions.md)) |
| Limite de indicadores e de tamanho da URL | divide os códigos em lotes, em [`endpoints.py`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/src/world_bank/extract/endpoints.py) |

## Estrutura das chamadas

Há duas formas equivalentes de filtrar:

| Forma | Exemplo |
|---|---|
| Por argumento | `/v2/country?incomeLevel=LIC` |
| Por caminho | `/v2/incomeLevel/LIC/country` |

O padrão para dados é `/v2/country/{países}/indicator/{indicadores}?{parâmetros}`.

| Símbolo | Significado | Exemplo |
|---|---|---|
| `;` | vários valores | `country/chn;bra` |
| `:` | intervalo | `date=2000:2010` |

O idioma vai logo depois de `/v2/`, como em `/v2/pt/country/br`. Nem todo nome está traduzido, e por isso este projeto traduz os nomes na própria base ([D-082](data-decisions.md)).

## Parâmetros

| Parâmetro | Valores | Observação |
|---|---|---|
| `format` | `xml` (padrão), `json`, `jsonP`, `jsonstat` | `jsonP` exige `prefix=NomeCallback` |
| `page` | inteiro | página a retornar |
| `per_page` | inteiro (padrão **50**) | registros por página |
| `date` | `2000`, `2012M01`, `2013Q1`, `2000:2010`, `YTD:2013` | ano, mês, trimestre, intervalo ou acumulado no ano |
| `mrv` | N | os N valores mais recentes |
| `mrnev` | N | os N valores mais recentes **não vazios** |
| `gapfill` | `Y` ou `N` | com `mrv`: preenche lacunas com o último valor |
| `frequency` | `Y`, `Q`, `M` | com `mrv`: anual, trimestral ou mensal |
| `source` | ID da base (`2` = WDI) | obrigatório ao pedir **vários indicadores** |
| `footnote` | `y` | inclui notas de rodapé |
| `downloadformat` | `csv`, `xml`, `excel` | com `source`: devolve um ZIP |

## Formato da resposta

A resposta em JSON é uma lista de 2 posições: `[metadados, dados]`.

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

Pontos que exigem atenção:

- `per_page` às vezes vem como texto (`"50"`), e às vezes como número.
- `latitude` e `longitude` vêm como texto, vazio nos agregados.
- `date` pode ser `2020`, `2020Q1` ou `2020M01`.

## Limites

- No máximo **60 indicadores** por requisição.
- No máximo **1.500 caracteres** entre duas barras do caminho.
- No máximo **4.000 caracteres** na URL inteira.
- **Não há ordenação:** os resultados vêm em ordem aproximadamente alfabética.
- A documentação não publica um limite de chamadas por tempo.

## Códigos de erro

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

O erro vem no corpo da resposta. **Na prática, a API pode devolver HTTP 200 mesmo com erro:** um indicador inválido, testado neste projeto, retorna 200 com `id: "120"`.

## Referências

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
