# Registro de erros e suposições da IA

Este registro é um requisito do curso. Para cada fase, anota o que a IA (Claude) assumiu errado ou não conseguiu verificar, como isso foi descoberto e o que foi feito.

## Fase 0 — Fundação

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| O plano dizia que o `README.md` não existia e que faltava criar o repositório no GitHub. Os dois já existiam (`origin` = `FranciscoAssislsj/World-Bank`). | `ls` e `git remote -v` antes de alterar arquivos. | O README existente foi ampliado em vez de recriado, e a criação do repositório foi pulada. |
| O plano esperava `plan.md`, `SKILL.md` e `doc_api.md` na raiz, mas eles estão em `.claude/`. | `git status` mostrou os arquivos fora da raiz. | Foram mantidos em `.claude/`. Os links da documentação apontam para lá. |
| Um heredoc do shell quebrou ao gerar vários arquivos de uma vez, e nenhum arquivo foi criado. | Erro `unexpected EOF` no shell e `find` retornando vazio. | Os arquivos foram reescritos com a ferramenta de escrita de arquivos. |
| A primeira versão do teste importava `tests.conftest`, mas `tests/` não é um pacote e o import falharia. | Revisão do código antes de entregar. | A constante passou a ser exposta por uma fixture (`fake_database_url`). |
| O código da Fase 0 foi escrito **sem ser executado pela IA**. Pelo modo de trabalho, quem roda `uv`, `ruff` e `pytest` é o usuário. | Execução pelo usuário (Python 3.14.2, pytest 9.2.0). | `ruff format` reformatou 1 arquivo (`tests/test_config.py`), `ruff check` passou e o `pytest` deu **24 passed**, cobertura **99,01%**. |
| A IA disse que seriam "21 testes", mas são 24. Ela contou as funções de teste, não os casos gerados pelo `parametrize`. | A saída do `pytest` mostrou `collected 24 items`. | Contagem corrigida. Lição: o número de testes coletados inclui cada caso parametrizado. |
| A IA passou o comando `Copy-Item` (PowerShell), mas o usuário estava no Prompt de Comando (cmd.exe). | Erro `'Copy-Item' não é reconhecido` no terminal do usuário. | Usar `copy .env.example .env` no cmd. A partir de agora, a IA confere o shell do usuário (prompt `C:\...>` = cmd, `PS C:\...>` = PowerShell). |
| O executável `docker` não foi encontrado no PATH (Git Bash e PowerShell). | `docker --version` falhou no ambiente da IA (antes da instalação). | O usuário instalou o Docker Desktop (29.9.2, WSL 2). O primeiro `compose up` falhou com `pipe/docker_engine` porque o motor (daemon) não estava rodando. Depois de abrir o Docker Desktop, o container `world_bank_postgres` (postgres:17) subiu. |

## Fase 1 — Cliente da API (extract)

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| O plano descrevia `SI.POV.DDAY` como pobreza extrema sem dizer a linha. A IA assumia a linha antiga de US$ 2,15/dia. | Teste de fumaça contra a API real: o nome atual é "Poverty headcount ratio at $3.00 a day (2021 PPP)". | Registrado em `data-decisions.md` (D-005). Os rótulos da gold vão usar US$ 3,00/dia. |
| A IA escreveu linhas acima de 88 caracteres em 3 arquivos novos. | `ruff format` reformatou `client.py`, `test_client.py` e `test_endpoints.py`. | Formatação aplicada pelo ruff. O `ruff check` passou sem erros. |
| O código de CO₂ `EN.GHG.CO2.PC.CE.AR5` era uma suposição ("confirmar") herdada do plano. | Chamada real a `/v2/indicator/EN.GHG.CO2.PC.CE.AR5`. | Confirmado, junto com os outros 14 códigos (D-003, D-004). |

## Fase 2 — Bronze

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A IA passou o comando `uvx postgres-mcp --access-mode=restricted` para configurar o MCP do Postgres sem testá-lo. O pacote não funciona: o `uvx` resolveu a versão 0.1.0, que quebra com a biblioteca `mcp` 2.x (`'Server' object has no attribute 'list_resources'`) e não tem a opção `--access-mode`. As versões 0.2.1 e 0.3.0 exigem `pglast==7.2`, que não existe mais no PyPI, então não instalam em nenhum computador. | `claude mcp list` mostrou `✗ Failed to connect`. A IA rodou o servidor à mão e leu o erro de cada versão. | O MCP passou a usar a imagem Docker oficial `crystaldba/postgres-mcp`, que já traz as dependências. Ela entra na rede do compose (`--network world_bank_default`) e acessa o banco pelo nome do container (`world_bank_postgres`), porque `host.docker.internal` resolvia para um IPv6 inacessível. Lição: testar o comando antes de passá-lo ao usuário. |
| A IA configurou o container na porta 5432 sem conferir se ela estava livre. Havia um PostgreSQL 18 instalado no Windows (serviço `postgresql-x64-18`) ouvindo na mesma porta, e ele atendia as conexões a `localhost:5432`. | O primeiro `migrate` falhou com `autenticação do tipo senha falhou para o usuário "wb"`. A mensagem em português indicou que não era o container (que responde em inglês). O `netstat` mostrou dois processos na 5432, e a senha funcionou dentro do container. | O container passou a expor a porta **5433** (`docker-compose.yml`, `.env.example`, `DATABASE_URL`). O PostgreSQL do Windows ficou intacto, e o MCP não mudou, porque usa a rede interna do Docker. |
| A primeira versão do agrupamento de páginas usava `itertools.groupby`, que só entrega um grupo quando vê a primeira página do grupo seguinte. Se a requisição seguinte falhasse logo no início, a anterior, já completa, não seria gravada, contrariando a spec. | O teste `test_run_bronze_stops_on_definitive_error` falhou: gravou `region` e `incomelevel`, mas não `lendingtypes`. | O agrupamento passou a entregar a requisição assim que chega a última página dela (`page >= pages`), com dois testes novos para esse caso. |

Validação executada pela IA a pedido do usuário ("valide"): `uv sync --locked` passou, `ruff format --check` e `ruff check` passaram, o `pytest` deu **63 passed** com cobertura de **99,61%**. O teste de fumaça contra a API real (só leitura) retornou: 44 regiões, 7 níveis de renda, 4 tipos de empréstimo, 296 países e agregados, 71 fontes, 21 tópicos, 266 observações de `SP.POP.TOTL` em 2023, e o código inválido gerou `ApiResponseError` com `code=120`.
