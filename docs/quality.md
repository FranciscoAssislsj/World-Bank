# Qualidade dos dados

Cada regra é um arquivo em [`sql/quality/`](https://github.com/FranciscoAssislsj/World-Bank/tree/main/sql/quality), que devolve as linhas com problema ([D-049](data-decisions.md)). O resultado de cada execução fica em `etl.quality_check` ([D-054](data-decisions.md)).

## Erro e aviso

| Nível | O que é | O que acontece |
|---|---|---|
| **Erro** | o que não pode ser verdade, como um percentual acima de 100 | o comando falha, e a gold não é recriada |
| **Aviso** | o que pode ser real e merece atenção | fica registrado, e o pipeline continua |

Essa separação evita alarme falso: se tudo bloqueasse, um valor estranho pararia o pipeline, e as pessoas passariam a ignorar as falhas ([D-051](data-decisions.md)).

## As 16 regras

### Erros (8)

| Regra | Pergunta |
|---|---|
| `bronze_completa` | Alguma carga tem menos páginas ou registros do que a API informou? |
| `completude_fato` | Falta linha de algum país real, indicador ou ano do período? |
| `faixa_ano` | Algum ano está fora de 1960 até o ano atual? |
| `faixa_expectativa_vida` | A expectativa de vida está fora de 0 a 120 anos? |
| `faixa_nao_negativo` | O CO2 per capita é negativo? |
| `faixa_percentual` | Algum percentual está fora de 0 a 100? |
| `faixa_positivo` | População, PIB ou PIB per capita são zero ou negativos? |
| `fato_diverge_bronze` | Algum valor do período difere da carga mais recente da bronze? |

### Avisos (8)

| Regra | Pergunta |
|---|---|
| `cobertura_baixa` | Algum indicador tem valor em menos da metade dos países em um ano? |
| `dimensao_fora_da_fonte` | Há país ou indicador que sumiu da carga mais recente da bronze? |
| `entidade_sem_valor` | Algum país ou agregado não tem nenhum valor? |
| `execucao_presa` | Alguma execução está como `running` há mais de 1 hora? |
| `fato_fora_da_fonte` | Há linha do fato no período que sumiu da bronze? |
| `pais_ano_sem_renda` | Quais pares de país real e ano do período não têm classificação de renda? |
| `renda_atual_diverge` | A renda atual de um país difere do ano mais recente do histórico? |
| `valor_atipico` | Há valor improvável, que merece investigação? |

## Avisos atuais

Situação na execução de 2026-11-07, com o período de 2000 a 2024. Todas as regras de erro passaram, e 4 avisos têm ocorrências:

| Aviso | Ocorrências | O que significa |
|---|---|---|
| `valor_atipico` | 29 valores | Cada caso foi investigado, e todos ficam nas contas, com o número da fonte e uma marca ([D-062](data-decisions.md)). A lista está em `gold.valores_atipicos`. |
| `cobertura_baixa` | 76 pares de indicador e ano | Alfabetização, pobreza, Gini e gastos com saúde têm valor em menos da metade dos países em alguns anos, inclusive em 2024. |
| `pais_ano_sem_renda` | 129 pares de país e ano | O histórico oficial não classifica o país naquele ano. |
| `entidade_sem_valor` | 1 agregado | `Not classified` não tem nenhum valor. |

Para ver a situação atual no seu banco:

```sql
select check_name, severity, passed, rows_failed, checked_at
from etl.quality_check
order by checked_at desc
limit 16;
```

## O valor da fonte nunca muda

O dado do World Bank é tratado como fiel ([D-070](data-decisions.md)). O projeto aponta o valor estranho, mas não o altera nem o exclui.

Isso tem uma consequência ao ler médias: a de um grupo pequeno pode ser puxada por um único país. Em 2012, o CO₂ per capita de Palau leva a média do seu grupo de 9 países a 24,90, com mediana de 1,32. Por isso, `gold.resumo_renda_regiao` traz `mediana` e `valores_atipicos` ao lado de `media` ([D-061](data-decisions.md)).

A investigação de cada caso está no fim de [Decisões sobre o dado](data-decisions.md#investigacao-dos-valores-atipicos-d-062).

## A soma dos países bate com o oficial?

`gold.reconciliacao_agregados` compara a soma dos países com o número oficial de cada agregado, em população e PIB. Uma diferença não é necessariamente um erro: Taiwan, por exemplo, não é listada como país, mas entra nos agregados do mundo e da renda alta.
