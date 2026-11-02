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
| O executável `docker` não foi encontrado no PATH (Git Bash e PowerShell). | `docker --version` falhou no ambiente da IA. | O usuário instalou o Docker Desktop (29.9.2, WSL 2). O primeiro `compose up` falhou com `pipe/docker_engine` porque o motor (daemon) não estava rodando. Depois de abrir o Docker Desktop, o container `world_bank_postgres` (postgres:17) subiu. |
