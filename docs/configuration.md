# Configuração

A configuração fica em dois lugares, e a separação é por segurança: o que é segredo fica no `.env`, que não vai para o git, e o resto fica em `configs/`, que vai.

## Variáveis do `.env`

Copie o `.env.example` para `.env` e ajuste os valores.

| Variável | Quem usa | O que é |
|---|---|---|
| `WB_ENV` | pipeline | qual arquivo de `configs/` usar: `dev` ou `prod` |
| `POSTGRES_USER` | Docker | usuário dono do banco |
| `POSTGRES_PASSWORD` | Docker | senha desse usuário |
| `POSTGRES_DB` | Docker | nome do banco |
| `DATABASE_URL` | pipeline | endereço completo do banco, com o usuário dono |
| `DASHBOARD_DATABASE_URL` | dashboards e `migrate` | endereço com o usuário `dashboard_leitor`, que só lê a gold ([D-079](data-decisions.md)). O `migrate` define a senha dele a partir daqui |
| `COMPOSE_PROFILES` | Docker | opcional: com o valor `mcp`, liga também a [ponte MCP](development.md#consultar-o-banco-pelo-claude-code) |

Quando `POSTGRES_PASSWORD` mudar, mude também a `DATABASE_URL`: as duas precisam da mesma senha.

## Arquivos de `configs/`

`configs/dev.toml` e `configs/prod.toml` têm as mesmas chaves. Só mudam o nível de log e o tempo de espera da API.

| Chave | `dev` | `prod` | O que é |
|---|---|---|---|
| `api_base_url` | `https://api.worldbank.org/v2` | igual | endereço da API |
| `request_timeout` | `30.0` | `60.0` | segundos de espera por resposta |
| `per_page` | `1000` | igual | registros por página |
| `max_retries` | `5` | igual | tentativas em erro temporário |
| `income_history_url` | arquivo `OGHIST` | igual | histórico oficial de renda, com versão nova todo mês de julho ([D-037](data-decisions.md)) |
| `source_id` | `2` | igual | base da API; `2` é a WDI ([D-001](data-decisions.md)) |
| `start_year`, `end_year` | `2000`, `2024` | igual | período das observações ([D-002](data-decisions.md)) |
| `log_level` | `DEBUG` | `INFO` | quanto detalhe aparece no log |
| `indicators` | 15 códigos | igual | indicadores buscados na API |

## Qual valor vale

Uma variável de ambiente ou uma linha do `.env` vale mais que o arquivo TOML. Qualquer chave pode ser trocada com o prefixo `WB_`, sem editar o arquivo. Por exemplo, no Git Bash:

```bash
WB_LOG_LEVEL=INFO uv run python -m world_bank validate
```

O período também pode mudar em cada execução, com `--start` e `--end`. Veja [Pipelines](pipelines.md).
