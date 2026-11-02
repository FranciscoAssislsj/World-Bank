---
name: world-bank-data-engineering
description: Regras, ferramentas e padrões obrigatórios para implementar e manter o pipeline de dados World Bank (Python, uv, pyenv, ruff, pytest, MkDocs Material). Use antes de criar, alterar, testar ou documentar qualquer código deste repositório.
---

# SKILL — Engenharia de Dados: projeto `world-bank`

Este documento é a referência para agentes de IA que trabalham neste repositório. Ele vale para implementação, manutenção e evolução do projeto.

**Convenção usada aqui:**

- **[OBRIGATÓRIO]**: regra que não pode ser quebrada. Se for preciso quebrá-la, pare e peça autorização ao usuário.
- **[RECOMENDADO]**: boa prática padrão. Pode ser adaptada quando houver justificativa, e a justificativa deve ser registrada.

**Contexto do projeto:**

- Pipeline de dados que consome a **World Bank Indicators API v2** (`https://api.worldbank.org/v2`). A API não exige autenticação, pagina os resultados e usa XML como formato padrão. Os detalhes estão em `doc_api.md`.
- Python **3.14**, definido em `.python-version`.
- Nome do projeto: `world-bank`. Nome do pacote importável: `world_bank`.

---

## 0. Fluxo de trabalho do agente (resumo executável)

```bash
# 1. Antes de alterar qualquer coisa
git status
cat pyproject.toml .python-version
uv sync

# 2. Durante o desenvolvimento
uv add <pacote>              # dependência de runtime
uv add --dev <pacote>        # dependência de desenvolvimento
uv run python -m world_bank  # executar o projeto

# 3. Antes de declarar a tarefa concluída
uv run ruff format .
uv run ruff check . --fix
uv run ruff format --check .
uv run ruff check .
uv run pytest
uv run mkdocs build --strict   # se docs/ ou mkdocs.yml mudaram
```

---

## 1. Gerenciamento do projeto: uv

### [OBRIGATÓRIO]

- Use **apenas o `uv`** para dependências, ambiente virtual e execução.
- O `pyproject.toml` é o arquivo central de configuração (dependências, ruff, pytest, coverage).
- **Versione o `uv.lock`** e nunca o adicione ao `.gitignore`.
- Não edite o `uv.lock` à mão.
- Não use `pip install`, `poetry`, `pipenv`, `conda` nem `requirements.txt` como fonte de verdade.

| Ação | Comando |
|---|---|
| Criar/sincronizar o ambiente | `uv sync` |
| Sincronizar exatamente como no lock (CI) | `uv sync --locked` |
| Adicionar dependência de runtime | `uv add httpx` |
| Adicionar dependência de desenvolvimento | `uv add --dev pytest pytest-cov` |
| Remover dependência | `uv remove <pacote>` |
| Atualizar o lock | `uv lock --upgrade-package <pacote>` |
| Executar ferramenta ou script | `uv run <comando>` |

### [RECOMENDADO]

- Agrupe as ferramentas de desenvolvimento no grupo `dev`, que é o padrão do `uv add --dev`.
- Fixe limites inferiores de versão (`>=`) e evite pins exatos no `pyproject.toml`. O `uv.lock` já garante a reprodutibilidade.

---

## 2. Versão do Python: pyenv

### [OBRIGATÓRIO]

- A versão do projeto é a que está em `.python-version` (atualmente `3.14`). O arquivo fica na raiz e é versionado.
- Instale e selecione a versão com o `pyenv`:

  ```bash
  pyenv install 3.14
  pyenv local 3.14     # grava/atualiza .python-version
  python --version
  ```

  No Windows, use o `pyenv-win`, que tem os mesmos comandos.
- O `requires-python` do `pyproject.toml` deve ser compatível com o `.python-version`.
- O `uv` lê o `.python-version` automaticamente ao criar a `.venv`. Para conferir:

  ```bash
  uv run python --version
  ```

- **Não altere a versão do Python** (nem `.python-version`, nem `requires-python`, nem `target-version` do ruff) sem verificar a compatibilidade de todas as dependências e sem autorização do usuário.

---

## 3. Ambiente virtual: `.venv`

### [OBRIGATÓRIO]

- Todas as dependências Python ficam em `.venv/`, que é criada e gerenciada pelo `uv` (`uv sync`).
- Nunca instale pacotes do projeto globalmente nem com `--user`.
- Não ative manualmente outros ambientes. Prefira `uv run`, que sempre usa a `.venv` do projeto.
- `.venv/` deve estar no `.gitignore` (já está).
- Se a `.venv` estiver corrompida ou com o Python errado, recrie:

  ```bash
  rm -rf .venv
  uv sync
  ```

---

## 4. Qualidade de código: Ruff

### [OBRIGATÓRIO]

O `ruff` é a **única** ferramenta de lint e formatação. Não use black, isort, flake8 nem pylint.

| Ação | Comando |
|---|---|
| Verificar problemas | `uv run ruff check .` |
| Corrigir automaticamente | `uv run ruff check . --fix` |
| Formatar | `uv run ruff format .` |
| Validar formatação | `uv run ruff format --check .` |

- Não desative regras globalmente para "passar" o lint.
- Use `# noqa: <CÓDIGO>` só em casos pontuais e justificados, sempre com o código específico, nunca um `# noqa` genérico.

### Configuração de referência (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 88
target-version = "py314"
src = ["src", "tests"]
extend-exclude = [".venv", "build", "dist", "site", "data"]

[tool.ruff.lint]
select = [
    "E", "W",   # pycodestyle
    "F",        # pyflakes
    "I",        # isort (organização de imports)
    "N",        # pep8-naming
    "UP",       # pyupgrade
    "B",        # flake8-bugbear
    "SIM",      # flake8-simplify
    "C4",       # flake8-comprehensions
    "PTH",      # usar pathlib em vez de os.path
    "S",        # flake8-bandit (segurança)
    "RUF",      # regras específicas do ruff
]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # assert é permitido em testes

[tool.ruff.lint.isort]
known-first-party = ["world_bank"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
```

Se o `ruff` instalado ainda não suportar `py314`, use a maior versão suportada e avise o usuário.

### [RECOMENDADO] Código limpo

- Funções pequenas, com uma responsabilidade e nomes descritivos.
- Prefira funções puras nas transformações. Elas são mais fáceis de testar.
- Use `pathlib.Path` em vez de manipular strings de caminho.
- Evite código morto, comentários óbvios e prints de depuração. Use `logging`.

---

## 5. Testes automatizados: pytest

### [OBRIGATÓRIO]

- Os testes ficam em `tests/` e espelham a estrutura de `src/world_bank/`.
- Use `pytest` com `pytest-cov`. A cobertura mínima é **70%** do código em `src/world_bank`.
- A verificação **falha automaticamente** quando a cobertura fica abaixo de 70% (veja a configuração abaixo).
- Testes unitários **não acessam a rede, bancos ou serviços externos**. Toda chamada HTTP à API do World Bank deve ser mockada.
- Toda função de extração, transformação, validação ou carga criada ou alterada precisa de teste correspondente.
- Corrigiu um bug? Adicione um teste que reproduza o bug.

```bash
uv add --dev pytest pytest-cov
uv run pytest                                  # usa a configuração do pyproject
uv run pytest --cov=src/world_bank --cov-report=term-missing --cov-fail-under=70
uv run pytest tests/transform -k "nome_do_teste" -vv
```

### Configuração de referência (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--cov=world_bank",
    "--cov-report=term-missing",
    "--cov-fail-under=70",
]
markers = [
    "integration: testes que acessam serviços reais (excluídos por padrão)",
]

[tool.coverage.run]
source = ["src/world_bank"]
branch = true

[tool.coverage.report]
show_missing = true
skip_empty = true
exclude_also = [
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### Padrões de teste

```python
# tests/conftest.py
import pytest


@pytest.fixture
def indicator_page() -> list:
    """Resposta JSON da API v2: [metadados, registros]."""
    return [
        {"page": 1, "pages": 1, "per_page": 50, "total": 1},
        [
            {
                "indicator": {"id": "SP.POP.TOTL", "value": "Population, total"},
                "country": {"id": "BR", "value": "Brazil"},
                "countryiso3code": "BRA",
                "date": "2023",
                "value": 216422446,
            }
        ],
    ]
```

```python
# tests/extract/test_client.py
from world_bank.extract.client import fetch_indicator


def test_fetch_indicator_returns_records(mocker, indicator_page):
    response = mocker.Mock(status_code=200)
    response.json.return_value = indicator_page
    mocker.patch("world_bank.extract.client.httpx.get", return_value=response)

    records = fetch_indicator("BR", "SP.POP.TOTL")

    assert records[0]["countryiso3code"] == "BRA"
```

### [RECOMENDADO]

- Use `pytest-mock` (`mocker`) ou `respx` (para `httpx`) para mockar HTTP.
- Use `tmp_path` para testar escrita em disco. Nunca escreva em diretórios reais do projeto.
- Use `@pytest.mark.parametrize` para casos de borda: `value` nulo, página vazia, paginação com várias páginas, erro HTTP.
- Marque testes de integração com `@pytest.mark.integration` e rode-os à parte: `uv run pytest -m integration`.

---

## 6. Documentação: MkDocs Material

### [OBRIGATÓRIO]

- A documentação fica em `docs/` e é configurada em `mkdocs.yml` na raiz.
- Atualize a documentação sempre que mudar comportamento, configuração, fontes, transformações, destinos ou comandos.
- Quando a documentação for alterada, `uv run mkdocs build --strict` precisa passar.

```bash
uv add --dev mkdocs mkdocs-material
uv run mkdocs serve      # http://127.0.0.1:8000
uv run mkdocs build      # gera site/ (adicione site/ ao .gitignore)
```

### Estrutura mínima de `docs/`

```text
docs/
├── index.md            # visão geral e objetivo
├── installation.md     # pyenv, uv, uv sync
├── configuration.md    # variáveis de ambiente e configs/
├── architecture.md     # camadas extract/transform/load e fluxo de dados
├── pipelines.md        # cada pipeline: fonte, transformações, destino, agenda
├── data-sources.md     # World Bank API v2 (endpoints, paginação, limites)
└── development.md      # lint, testes, cobertura, convenções
```

### `mkdocs.yml` de referência

```yaml
site_name: World Bank Data Pipeline
repo_url: ""  # preencher quando houver repositório remoto
theme:
  name: material
  language: pt-BR
  features:
    - navigation.sections
    - content.code.copy
    - search.highlight
markdown_extensions:
  - admonition
  - tables
  - toc:
      permalink: true
  - pymdownx.highlight
  - pymdownx.superfences
nav:
  - Início: index.md
  - Instalação: installation.md
  - Configuração: configuration.md
  - Arquitetura: architecture.md
  - Pipelines: pipelines.md
  - Fontes de dados: data-sources.md
  - Desenvolvimento: development.md
```

O conteúdo de `doc_api.md` deve ser migrado ou referenciado em `docs/data-sources.md`, sem duplicar.

---

## 7. Boas práticas de Engenharia de Dados

Adapte cada item à complexidade real do projeto e não introduza frameworks ou infraestrutura sem necessidade.

### 7.1 Organização ETL/ELT [OBRIGATÓRIO]

- Separe **extração**, **transformação** e **carga** em módulos distintos.
- A **extração** só busca dados e devolve dados brutos, sem regra de negócio.
- A **transformação** é feita de funções puras (entrada → saída), sem I/O, e é testável sem mocks.
- A **carga** só persiste dados e não transforma.
- O **pipeline** (orquestração) compõe as três etapas e não contém regra de negócio.

```python
# src/world_bank/pipelines/population.py
def run(countries: list[str], start: int, end: int, settings: Settings) -> Path:
    raw = extract.fetch_indicator(countries, "SP.POP.TOTL", start, end)
    df = transform.normalize_indicator(raw)
    validate.check_indicator_schema(df)
    return load.write_parquet(df, settings.data_dir / "population", partition="year")
```

### 7.2 Cliente da World Bank API [OBRIGATÓRIO]

- Sempre envie `format=json` e um `per_page` explícito, e trate a **paginação** até `page == pages`.
- A resposta JSON é `[metadados, registros]`. Trate `registros` como `None` ou vazio.
- Uma resposta de erro chega como `[{"message": [...]}]` com status 200. Detecte esse caso e lance exceção.
- Configure **timeout** em toda requisição e **retry com backoff** para erros transitórios (5xx, timeout).
- Centralize URL base, timeout e `per_page` em configuração, não espalhados pelo código.

### 7.3 Configurações por ambiente [OBRIGATÓRIO]

- Configurações não sensíveis ficam em `configs/` (ex.: `configs/dev.toml`, `configs/prod.toml`) ou em valores padrão tipados.
- O ambiente é selecionado por variável (ex.: `WB_ENV=dev`).
- Carregue as configurações em um único ponto (`world_bank/config.py`), em um objeto tipado (dataclass ou `pydantic-settings`).

### 7.4 Credenciais e segredos [OBRIGATÓRIO]

- **Nunca** coloque credenciais, tokens ou senhas no código, em `configs/`, em testes ou na documentação.
- Segredos vêm de variáveis de ambiente. Um `.env` local é aceito, mas deve estar no `.gitignore`.
- Mantenha um `.env.example` versionado, apenas com nomes de variáveis e valores fictícios.
- Não registre segredos em logs nem em mensagens de exceção.

### 7.5 Logging e exceções [OBRIGATÓRIO]

- Use o módulo `logging`, com `logger = logging.getLogger(__name__)` por módulo. Não use `print` no código de produção.
- Prefira logs estruturados, com contexto em campos: pipeline, indicador, país, página, nº de registros, duração.
- Configure o logging uma única vez, no ponto de entrada.
- Não engula exceções (`except Exception: pass`). Capture exceções específicas, adicione contexto e relance ou trate.
- Defina exceções do domínio em `world_bank/exceptions.py` (ex.: `ApiResponseError`, `SchemaValidationError`).

```python
logger.info(
    "indicator extracted",
    extra={"indicator": indicator, "countries": len(countries), "records": len(rows)},
)
```

### 7.6 Validação de esquema e qualidade [OBRIGATÓRIO]

- Valide os dados **após a extração** (estrutura da resposta) e **antes da carga** (esquema final).
- No mínimo, verifique colunas obrigatórias, tipos, chaves sem nulos (`country_iso3`, `indicator_id`, `year`), unicidade da chave e faixas plausíveis (ano, valores não negativos quando aplicável).
- Dados inválidos devem falhar o pipeline de forma explícita, ou ser separados em quarentena, com log. Nunca devem passar silenciosamente.

[RECOMENDADO] Use `pydantic` para registros da API e `pandera` (ou checagens explícitas) para DataFrames.

### 7.7 Idempotência e reprocessamento [OBRIGATÓRIO]

- Executar o mesmo pipeline com os mesmos parâmetros deve produzir **o mesmo resultado**, sem duplicar dados.
- Grave de forma particionada (ex.: por `indicator` e `year`) com **sobrescrita da partição**, ou faça upsert por chave natural (`country_iso3`, `indicator_id`, `year`).
- Escreva em arquivo temporário e renomeie no final (escrita atômica).
- Parametrize o período (`start`, `end`) para permitir backfill e reprocessamento.
- Separe as camadas de dados: `raw` (resposta original), `processed` (normalizado) e `curated` (pronto para consumo), se aplicável.

### 7.8 Regras de negócio vs. infraestrutura [OBRIGATÓRIO]

- Regras de negócio (cálculos, normalização, filtros) não importam clientes HTTP, drivers de banco nem SDKs de nuvem.
- Adaptadores de infraestrutura (HTTP, filesystem, banco) ficam isolados e são injetados por parâmetro, o que facilita os mocks.

### 7.9 Tipagem e docstrings [OBRIGATÓRIO]

- Toda função pública tem **type hints** completos e usa a sintaxe moderna (`list[str]`, `X | None`).
- Toda função pública tem **docstring** (estilo Google) descrevendo propósito, argumentos, retorno e exceções.

```python
def normalize_indicator(records: list[dict]) -> pd.DataFrame:
    """Converte registros da API v2 em um DataFrame tabular.

    Args:
        records: Registros brutos retornados pelo endpoint de indicadores.

    Returns:
        DataFrame com as colunas country_iso3, indicator_id, year e value.

    Raises:
        SchemaValidationError: Se campos obrigatórios estiverem ausentes.
    """
```

### 7.10 Rastreabilidade da camada gold [OBRIGATÓRIO]

Critério principal do curso: **cada indicador tem um arquivo `.sql` de onde saiu, cada decisão sobre o dado tem um motivo escrito, e o histórico do git conta a ordem em que as coisas aconteceram.**

- A camada gold é definida **somente** em `sql/gold/`, com **um arquivo `.sql` por view** (`sql/gold/<nome>.sql` cria `gold.<nome>`).
- Todo arquivo de `sql/gold/` começa com um cabeçalho de comentário contendo: pergunta de negócio, grão (o que é uma linha), tabelas de origem e regras aplicadas.
- Nenhum indicador é calculado fora de `sql/gold/` (nem em Python, nem no Streamlit, nem no Power BI). Faltou um indicador? Crie ou altere o `.sql`.
- Toda decisão sobre o dado (filtro, exclusão, tratamento de nulo, escolha de código, agregação) é registrada em `docs/data-decisions.md` com motivo e alternativa descartada, na mesma fase em que é tomada.
- Um commit por etapa, com mensagem descritiva. Não reescreva o histórico (sem squash, rebase ou force push).
- Commits vão para o branch `dev`. A `main` recebe `dev` só por Pull Request com merge commit, depois de lint e testes passarem.

### 7.11 Proibições [OBRIGATÓRIO]

- Sem caminhos absolutos. Use caminhos relativos à raiz do projeto ou vindos de configuração.
- Sem credenciais hardcoded.
- Sem código duplicado. Extraia funções utilitárias.
- Sem dados reais versionados. Adicione `data/` ao `.gitignore`, exceto pequenas fixtures em `tests/fixtures/`.

---

## 8. Estrutura do projeto

Estrutura-alvo (layout `src/`). Crie os diretórios **conforme forem necessários**, sem estruturas vazias.

```text
world_bank/
├── src/
│   └── world_bank/
│       ├── __init__.py
│       ├── __main__.py        # ponto de entrada (substitui o main.py da raiz)
│       ├── config.py          # carregamento de configurações tipadas
│       ├── exceptions.py
│       ├── extract/           # cliente da World Bank API
│       ├── transform/         # funções puras de transformação
│       ├── validate/          # esquemas e checagens de qualidade
│       ├── load/              # escrita em arquivos/banco
│       └── pipelines/         # orquestração extract → transform → load
├── tests/
│   ├── conftest.py
│   ├── fixtures/              # respostas JSON de exemplo da API
│   ├── extract/
│   ├── transform/
│   └── load/
├── docs/                      # MkDocs (inclui ai-log.md e data-decisions.md)
├── sql/
│   ├── migrations/            # NNN_*.sql: schemas e tabelas (bronze, silver, etl)
│   └── gold/                  # um .sql por view da camada gold
├── configs/                   # configs não sensíveis por ambiente
├── scripts/                   # scripts auxiliares (backfill, utilitários)
├── .env.example
├── .gitignore
├── .python-version
├── mkdocs.yml
├── pyproject.toml
├── uv.lock
├── README.md
├── SKILL.md
└── doc_api.md                 # migrar para docs/data-sources.md
```

**Para migrar para o layout `src/`**, configure o build backend no `pyproject.toml` para que o `uv sync` instale o pacote em modo editável:

```toml
[build-system]
requires = ["uv_build>=0.9,<1"]
build-backend = "uv_build"
```

Ao mover `main.py` para `src/world_bank/__main__.py`, execute com `uv run python -m world_bank`.

**`.gitignore`: entradas mínimas além das existentes:**

```gitignore
.env
.coverage
htmlcov/
.pytest_cache/
.ruff_cache/
site/
data/
```

---

## 9. Regras obrigatórias para agentes de IA

1. **Inspecione antes de modificar.** Leia `pyproject.toml`, `.python-version`, `.gitignore`, a estrutura de `src/` e `tests/` e o `git status`. Não sobrescreva configurações existentes sem necessidade.
2. **Respeite o `uv` e o `pyenv`.** Use dependências via `uv add` e execução via `uv run`, com a versão definida em `.python-version`.
3. **Nada fora da `.venv`.** Não use `pip install` global nem `--user`.
4. **Use o `ruff`** para lint e formatação, e nenhuma outra ferramenta.
5. **Teste junto com o código.** Toda funcionalidade nova ou alterada vem com testes novos ou atualizados.
6. **Mantenha a cobertura em pelo menos 70%.** Não reduza o limite e não exclua arquivos da cobertura para atingi-lo.
7. **Atualize a documentação** em `docs/` (e o `README.md`, se for o caso) quando houver mudança relevante.
8. **Preserve a arquitetura.** Siga a separação extract/transform/validate/load/pipelines e os padrões existentes.
9. **Prefira o simples.** Escolha soluções modulares e testáveis. Não adicione dependências, frameworks ou abstrações sem necessidade clara.
10. **Não exponha segredos.** Credenciais e tokens não entram no código, em logs, em commits, na documentação nem nas respostas ao usuário.
11. **Verifique antes de concluir.** Execute todas as checagens da seção 10.
12. **Seja transparente.** Se algum teste ou verificação não puder ser executado ou falhar, diga explicitamente qual, por quê e mostre a saída relevante. Nunca declare sucesso sem evidência.

Também é proibido, sem autorização explícita do usuário: alterar a versão do Python, reduzir o limite de cobertura, desativar regras do ruff globalmente, fazer commit/push ou apagar dados e arquivos não criados pela tarefa.

---

## 10. Critérios de conclusão (Definition of Done)

Execute na ordem. Todos os itens aplicáveis precisam passar.

```bash
uv sync --locked                 # dependências sincronizadas com o lock
uv run ruff format --check .     # código formatado
uv run ruff check .              # lint sem erros
uv run pytest                    # testes aprovados + cobertura >= 70%
uv run mkdocs build --strict     # somente se docs/ ou mkdocs.yml mudaram
```

Checklist:

- [ ] Código formatado pelo Ruff (`ruff format --check` sem diferenças).
- [ ] Lint sem erros (`ruff check`).
- [ ] Todos os testes aprovados.
- [ ] Cobertura igual ou superior a **70%**.
- [ ] `uv.lock` atualizado e consistente com o `pyproject.toml` (`uv sync --locked` passa).
- [ ] Documentação atualizada quando aplicável.
- [ ] Build do MkDocs sem erros quando a documentação foi alterada.
- [ ] Nenhuma credencial, caminho absoluto ou dado sensível adicionado.
- [ ] Toda view da gold tem seu arquivo em `sql/gold/` com cabeçalho; toda decisão sobre o dado está em `docs/data-decisions.md` (§7.10).
- [ ] Relato final ao usuário com o que foi feito, os comandos executados com seus resultados e as pendências ou verificações não executadas.
