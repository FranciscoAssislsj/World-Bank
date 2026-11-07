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
uv sync
cp .env.example .env
docker compose up -d --wait
uv run python -m world_bank run-all
```

Os comandos instalam as dependências, criam o `.env`, sobem o banco e rodam o pipeline. No Prompt de Comando do Windows, troque `cp` por `copy`.

O `run-all` faz todo o caminho, da criação das tabelas até a gold, e para na primeira falha. Para rodar uma etapa de cada vez, veja [Pipelines](pipelines.md).

Antes de usar em algo além da sua máquina, troque as senhas do `.env`. Os valores do exemplo são fictícios.

## Conferir se deu certo

Se o comando terminou sem erro, a gold está pronta. Para ver os dados, abra os [dashboards](dashboards.md) ou consulte o banco:

```bash
docker compose exec postgres psql -U wb -d world_bank -c "select count(*) from gold.fato_observacao"
```

Se mudou o usuário ou o nome do banco no `.env`, troque `wb` e `world_bank`.

## Problemas comuns

| O que aparece | O que fazer |
|---|---|
| Falha de senha, porta ocupada ou conexão parada | Confira se o `.env` usa o mesmo endereço e a mesma porta do `.env.example`. Se outro programa já ocupar a porta, mude-a no `docker-compose.yml` e no `.env`. |
| Erro `pipe/docker_engine` no `docker compose` | Abra o Docker Desktop e espere o motor ligar. |
| O pipeline falha ao chamar a API | A API do World Bank pode estar fora do ar. O cliente já repete os erros temporários, então espere um pouco e rode de novo. |
