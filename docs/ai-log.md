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

Validação executada pela IA a pedido do usuário ("valide"): `uv sync --locked` passou, `ruff format --check` e `ruff check` passaram, o `pytest` deu **63 passed** com cobertura de **99,61%**. O teste de fumaça contra a API real (só leitura) retornou: 44 regiões, 7 níveis de renda, 4 tipos de empréstimo, 296 países e agregados, 71 fontes, 21 tópicos, 266 observações de `SP.POP.TOTL` em 2023, e o código inválido gerou `ApiResponseError` com `code=120`.
