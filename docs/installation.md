# Instalação

## O que instalar

| Programa | Para quê |
|---|---|
| [pyenv](https://github.com/pyenv-win/pyenv-win), com Python 3.14 | fixa a versão do Python, indicada em `.python-version` |
| [uv](https://docs.astral.sh/uv/) | cria a `.venv` e instala as versões exatas do `uv.lock` |
| [Docker](https://www.docker.com/products/docker-desktop/) | roda o PostgreSQL 17 sem instalá-lo no computador |
| [Power BI Desktop](https://www.microsoft.com/power-platform/products/power-bi/desktop) (opcional) | abre o relatório; só existe para Windows |

A API do World Bank não pede cadastro nem chave.

## Rodar do zero

```bash
uv sync                      # cria a .venv e instala as dependências
cp .env.example .env         # no Prompt de Comando do Windows: copy .env.example .env
docker compose up -d --wait  # sobe o PostgreSQL em 127.0.0.1:5433
uv run python -m world_bank run-all
```

O `run-all` faz todo o caminho, da criação das tabelas até a gold, e para na primeira falha. Para rodar uma etapa de cada vez, veja [Pipelines](pipelines.md).

Antes de usar em algo além da sua máquina, troque as senhas do `.env`. Os valores do exemplo são fictícios.

## Conferir se deu certo

Se o comando terminou sem erro, a gold está pronta. Para ver os dados, abra os [dashboards](dashboards.md) ou consulte o banco:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) from gold.fato_observacao"'
```

## Problemas comuns

| O que aparece | O que fazer |
|---|---|
| Falha de senha para o usuário `wb` | Confira se a conexão usa a porta **5433**. A 5432 costuma ser de outro PostgreSQL instalado no computador. |
| A conexão fica parada no Windows | Use `127.0.0.1` no endereço do banco, e não `localhost`. |
| O terminal continua usando um valor antigo do `.env` | Abra um terminal novo. O do VS Code pode guardar o valor anterior. |
| Erro `pipe/docker_engine` no `docker compose` | Abra o Docker Desktop e espere o motor ligar. |
| O pipeline falha ao chamar a API | A API do World Bank pode estar fora do ar. O cliente já repete os erros temporários, então espere um pouco e rode de novo. |
