# Desenvolvimento

## Conferências

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest                # testes unitários: sem rede e sem banco, cobertura >= 70%
uv run --group dashboard pytest -m integration --no-cov   # testes contra o PostgreSQL local
uv run mkdocs build --strict # monta o site e falha em qualquer aviso
```

Os testes de integração precisam da silver carregada. Sem ela, parte deles se pula sozinha. O `--no-cov` existe porque a cobertura mínima vale para os testes unitários: sem ele, o comando termina com erro mesmo com todos os testes passando.

## O site de documentação

```bash
uv run mkdocs serve -a 127.0.0.1:8001   # abre em http://127.0.0.1:8001
```

A porta 8001 evita conflito com a ponte MCP, que usa a 8000.

O site é publicado no [GitHub Pages](https://franciscoassislsj.github.io/World-Bank/) a cada envio para a `main`, pelo [workflow de documentação](https://github.com/FranciscoAssislsj/World-Bank/blob/main/.github/workflows/docs.yml) ([D-090](data-decisions.md)).

## Pre-commit

Ative uma vez, depois do `uv sync`:

```bash
uv run pre-commit install
uv run pre-commit run --all-files   # opcional: confere o projeto inteiro agora
```

A cada `git commit`, ele roda o Ruff, confere o `uv.lock` e barra arquivo `.env`, chave privada e arquivo grande ([D-075](data-decisions.md)). Se ele corrigir um arquivo, o commit para: rode `git add` nesse arquivo e faça o commit de novo.

## CI

O [CI](https://github.com/FranciscoAssislsj/World-Bank/blob/main/.github/workflows/ci.yml) roda a cada envio para `dev` e `main` e em cada pull request para a `main`, em uma máquina limpa:

1. Formatação, lint e testes unitários ([D-071](data-decisions.md)).
2. Sobe o banco, roda o `run-all` contra a API real e roda os testes de integração. Teste pulado faz o CI falhar ([D-072](data-decisions.md)).

Se a API do World Bank estiver fora do ar, o CI fica vermelho sem que o código tenha problema. Nesse caso, rode de novo.

## Convenções

- **Nomes:** tabelas e colunas da silver e da gold em português, em `snake_case` e sem acento ([D-015](data-decisions.md)). A bronze mantém os nomes da API.
- **Regra de negócio:** fica em `sql/gold/`, nunca no dashboard ([D-078](data-decisions.md)).
- **Novo arquivo da gold:** `NN_nome.sql`, com cabeçalho e uma única consulta ([D-069 e D-088](data-decisions.md)).
- **Nova regra de qualidade:** um arquivo em `sql/quality/`, com cabeçalho ([D-049](data-decisions.md)).
- **Mudança na estrutura do banco:** uma nova migração em `sql/migrations/`. Depois, atualize o dicionário com `uv run python scripts/gerar_dicionario.py`.
- **Decisão sobre o dado:** registre em `docs/data-decisions.md`, com o motivo e a alternativa descartada.
- **Erro da IA:** registre em `docs/ai-log.md`.
- **Branches:** commits no `dev`, e merge para a `main` por pull request, com merge commit.

## Consultar o banco pelo Claude Code

O `docker-compose.yml` traz uma ponte [MCP](https://modelcontextprotocol.io) só de leitura, usada por todas as sessões ([D-076](data-decisions.md)). Ela é opcional, e o pipeline não depende dela.

Para ativar, tire o `#` da linha `COMPOSE_PROFILES=mcp` no `.env`, rode `docker compose up -d --wait` e crie o `.mcp.json` na raiz do projeto, que não é versionado:

```json
{
  "mcpServers": {
    "postgres": { "type": "sse", "url": "http://127.0.0.1:8000/sse" }
  }
}
```
