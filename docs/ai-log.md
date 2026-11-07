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

## Fase 3 — Silver: dimensões

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| O plano usava o campo `id` como chave de `dim_region` (`region_id`). Esse campo está vazio em 37 das 44 regiões. | Perfilamento da bronze antes de escrever a spec. | A chave passou a ser o campo `code`, que é o que `country.region.id` referencia (D-016). |
| O plano previa chaves estrangeiras de país para região, renda e tipo de empréstimo sem considerar os agregados. Os 79 agregados usam `NA` ou vazio, códigos que não existem nessas dimensões, e a carga falharia. | Comparação dos códigos de `country` com os das dimensões. | Nos agregados, as três chaves ficam `NULL`, com `e_agregado = true` (D-017). |
| O plano definia a chave do fato como `(country_iso3, indicator_id, period)`. Cinco agregados de renda (1.875 linhas) têm `countryiso3code` vazio, e a chave colidiria em 375 combinações. | Contagem de chaves duplicadas nas observações. | A ser aplicado na Fase 4: achar o país pelo `country.id`, que corresponde ao `iso2Code` de `country` nos 266 códigos das observações. |
| A spec chamava a coluna de `nivel_renda_id` e dava como aceitável aplicar a classificação de hoje a todos os anos. Isso levaria a ler um país de renda alta hoje como se já fosse assim em 2000. | O responsável questionou a suposição. A pesquisa confirmou que a classificação é fixada por ano fiscal e que o histórico oficial (`OGHIST`) é um Excel fora da API. | As colunas passaram a `nivel_renda_atual_id` e `tipo_emprestimo_atual_id`, e o limite ficou escrito na D-025. |
| A spec excluía `adminregion` da silver dizendo que nenhuma pergunta o usava, sem considerar o apoio à análise em geral. | O responsável pediu tudo que apoie a análise. O perfilamento mostrou o campo preenchido em 131 países, com todos os códigos existindo em `region`. | O campo entrou como `regiao_administrativa_id` (D-020, D-034). |
| O motivo da D-015 dizia que a ausência de acento evita aspas no SQL. O Postgres aceita letras acentuadas em nomes sem aspas; o que dispensa aspas é usar minúsculas. | Revisão dos motivos, ao exigir que cada um se apoiasse em uma boa prática. | O motivo foi reescrito: minúsculas dispensam aspas, e a ausência de acento evita problemas de codificação entre ferramentas. |
| A D-030 apagava e reinseria toda a ponte a cada carga. Com as colunas de linhagem, `atualizado_em` mudaria em toda execução, mesmo sem mudança no dado. | Revisão ao acrescentar a D-033. | A ponte passou a inserir só as ligações novas e apagar só as que sumiram. |
| A spec previa dois arquivos `test_dimensions.py`. Como `tests/` não tem `__init__.py`, o pytest não aceita dois arquivos com o mesmo nome. | Conferência da estrutura de testes antes de escrevê-los. | O arquivo da transformação se chama `test_transform_dimensions.py`. |
| Ao limitar o Postgres a `127.0.0.1` no `docker-compose.yml`, a IA não ajustou o `DATABASE_URL`, que usava `localhost`. No Windows, `localhost` tentava primeiro o endereço IPv6, e a conexão ficava parada por cerca de 130 segundos antes de tentar o outro. | O `load-dimensions` parecia travado. Um rastreamento mostrou o programa parado na abertura da conexão, sem nenhuma sessão no banco. | O `DATABASE_URL` passou a usar `127.0.0.1` no `.env` e no `.env.example`, e o README foi corrigido. |
| A pesquisa da IA encontrou o `OGHIST` de julho de 2025 e o tratou como a versão disponível. | Teste do endereço com a data de 2026, antes de usar o arquivo. | O projeto usa `OGHIST_2026_07_01.xlsx`, que vai até o ano de referência 2025. |

Validação executada pela IA: `ruff format` e `ruff check` passaram, o `pytest` deu **192 passed** com cobertura de **99,33%**, e o `pytest -m integration` deu **10 passed**, sem deixar linhas de teste no banco. O `load-dimensions` gravou 44, 7, 4, 71, 21, 296, 7.990, 15 e 23 linhas, e a 2ª execução gravou 0. O `load-bronze` repetido gravou 0 requisições e não regravou o arquivo. A recontagem direta no Excel deu as mesmas 7.990 linhas, e os 217 países têm a mesma classificação no arquivo (ano de referência 2025) e na API.

## Fase 4 — Silver: fato de observações

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| O plano guardava `period` e `frequency`, supondo dados de várias frequências. | Perfilamento: as 99.750 linhas são todas anuais. | O fato usa só `ano`, e um dado trimestral interrompe a carga (D-040). |
| O plano decidia pular a carga comparando `lastupdated`. Essa data é da base inteira e não garante que uma correção seja detectada. | Revisão da spec, comparando com a detecção de mudança que a bronze já faz. | A comparação usa as cargas da bronze lidas na última execução (D-045). |
| A spec esperava 5 agregados de renda na conferência. São 7: os 5 eram só os que vêm sem ISO3, e `LMY` e `MIC` também são de renda. | A consulta de conferência devolveu 7 linhas. | O esperado da spec foi corrigido. Todos têm 375 observações. |

Validação executada pela IA: `ruff format` e `ruff check` passaram, o `pytest` deu **235 passed** com cobertura de **99,43%**, e o `pytest -m integration` deu **16 passed**, sem deixar linhas de teste no banco. O `load-observations` gravou 99.750 linhas; a 2ª execução foi pulada, e o `--full-refresh` leu 99.750 e gravou 0. A soma dos valores e a comparação linha a linha com a bronze deram 0 diferenças, a bronze continuou com 121 páginas, e o `EXPLAIN` mostrou o uso do índice `(indicador_id, ano)`.

## Fase 5 — Validação e qualidade

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| O plano previa modelos pydantic para os registros da API, sem considerar que a transformação já confere cada campo. | Comparação entre o plano e o código das Fases 3 e 4, ao escrever a spec. | Os modelos não foram criados (D-055). |
| O plano validava antes de gravar, o que impede comparar o dado novo com as outras tabelas e com a bronze. | Ao listar as regras: completude e divergência com a bronze precisam do dado já gravado. | O dado é gravado e inspecionado na mesma transação, e um erro desfaz tudo (D-050). |
| A primeira versão da spec previa só o período como parâmetro das regras. Se a lista de indicadores mudasse, um indicador retirado geraria falso erro de completude, e uma carga antiga geraria falsa divergência. | Revisão das consultas ao escrevê-las. | As regras recebem também os indicadores e os endpoints configurados. |

Validação executada pela IA: `ruff format` e `ruff check` passaram, o `pytest` deu **266 passed** com cobertura de **99%**, e o `pytest -m integration` deu **27 passed**, incluindo dado ruim plantado para cada regra de erro e um valor impossível que não chegou a ser publicado, sem deixar linhas no banco. Na primeira execução do `validate`, as 8 regras de erro passaram; os avisos foram `cobertura_baixa` 76, `valor_atipico` 29, `pais_ano_sem_renda` 129 e `entidade_sem_valor` 1. O fato continuou com 99.750 linhas, e a bronze, com 121 páginas.

## Fase 6 — Gold e CLI

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A IA recomendou manter os valores atípicos nas médias e só sinalizá-los, sem medir o efeito. | O responsável questionou. A medição mostrou que Palau leva a média de CO₂ do seu grupo de 9 países de 2,65 para 24,90 em 2012. | Os valores não comparáveis saem da análise e são avisados (D-062). |
| A IA então propôs remover os 29 valores apontados, tratando os limites como prova de erro. | O responsável pediu que cada caso fosse analisado. A investigação mostrou que o Catar é um boom real e que o valor de Seicheles é a estimativa oficial depois do censo. | Só 27 valores saem da análise; a população fica, e Seicheles sai apenas do ranking urbano (D-062). |
| Depois disso, a IA deixou os 27 valores vazios em `pais_ano` e, ao registrar a premissa de dado fiel (D-070), abriu uma exceção para encaixar as duas decisões. Vazio afirmava que a fonte não tinha o dado, e as decisões se contradiziam. | O responsável perguntou o que um engenheiro sênior faria. | A gold mantém o número da fonte, com uma marca, e oferece `media` e `media_sem_atipicos` lado a lado (D-062, D-070). |
| Ao corrigir isso, a IA seguiu a ideia de um "engenheiro sênior" e publicou duas médias, `media` e `media_sem_atipicos`. Duas médias dão duas respostas para a mesma pergunta. | O responsável decidiu usar uma só, fiel à base depois dos tratamentos. | Uma média só, com os valores da silver; o valor estranho é apontado e fica em todas as contas (D-062). |
| A IA manteve Seicheles fora do ranking de população urbana, como exceção à regra de não excluir valores, e recomendou continuar assim. | O responsável decidiu que a premissa de dado fiel vale também para o ranking. | Seicheles voltou ao ranking, e o valor segue apontado em `gold.valores_atipicos` (D-062). |
| A IA disse que a falta de cerca de 23 milhões de pessoas nos agregados "provavelmente" era Taiwan, por dedução. | Consulta à ajuda do World Bank, que confirma que Taiwan não é listada como país e entra nos agregados do mundo e da renda alta. | Registrado na D-066. O valor em si não foi comparado com a fonte de Taiwan. |
| A spec da Fase 5 previa terminar o `run-all` com `validate`, o que publicaria a gold antes de saber se há erro. | Revisão da ordem ao escrever esta spec. | `validate` roda antes de `build-gold` (D-068). |
| O plano previa o `create materialized view` dentro do arquivo `.sql`, e a primeira versão da spec também. | O responsável pediu uma única query por arquivo. | O arquivo traz só o cabeçalho e a query, e o Python cria o resto (D-069). |
| A spec nomeava `tests/pipelines/test_gold.py`, que colide com `tests/load/test_gold.py`, porque `tests/` não é um pacote. | Erro `import file mismatch` no `pytest`. | O arquivo virou `test_gold_pipeline.py`. |
| Um heredoc do shell quebrou de novo ao editar a spec com um script longo, sem alterar nada. | Erro `unexpected EOF` no shell. | O script foi escrito com a ferramenta de arquivos. |

**Decidido sem confirmar a causa:** Turks e Caicos tem +74,6% em 2017, e o Banco de Desenvolvimento do Caribe dava -1,5%. A diferença não foi explicada, e o responsável decidiu tratar o dado do World Bank como fiel (D-070).

**Em aberto, sem resposta confirmada:**

- **Seicheles:** a origem do valor foi lida só no resumo da busca, porque a página da agência de notícias recusou o acesso direto.
- **Palau:** o Our World in Data não nomeia, na página consultada, a base dos seus 12,76 t. Por isso a causa da diferença com o EDGAR não foi confirmada.

Validação executada pela IA: `ruff format --check` e `ruff check` passaram, o `pytest` deu **305 passed** com cobertura de **99%**, e o `pytest -m integration` deu **42 passed**. As migrações também rodaram em um banco vazio. O `run-all` rodou duas vezes contra a API e o banco reais, com código 0; a 2ª execução gravou 0 linhas na silver e deu as mesmas contagens na gold. As consultas de conferência deram o esperado. Cada arquivo de `sql/gold/` também rodou sozinho no `psql`, mas não foi aberto no DBeaver.

Durante o `run-all`, a API trouxe uma mudança real no cadastro de fontes: a bronze passou de 121 para 122 páginas, e 4 linhas de `dim_fonte` mudaram. As observações não mudaram.

## CI — GitHub Actions

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| Na Fase 6, a IA registrou que `pytest -m integration` deu "42 passed" e leu só a contagem. O comando termina com erro, porque a cobertura mínima de 70% vale também para ele (50% nesse caso). | Ensaio do CI em um Linux limpo, conferindo o código de saída de cada comando. | O README e o CI usam `--no-cov` nos testes de integração. |
| O registro da Fase 6 não dizia que 26 dos 42 testes de integração se pulam com a silver vazia, o que daria um CI verde sem testar a gold. | O mesmo ensaio, com o banco vazio: 16 passados e 26 pulados, com código de saída 0. | O CI carrega os dados antes dos testes e falha se algum teste for pulado (D-072). |

## Pre-commit

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A IA testou o hook do Ruff com um arquivo fora do repositório. O resultado foi "Passed", mesmo com um erro no arquivo: o Ruff corrigiu o arquivo, e o pre-commit só percebe a alteração em arquivos dentro do repositório. | O resultado contrariava o esperado, e o arquivo aparecia alterado. | O teste foi refeito com `git commit` de verdade em um clone descartável. |

Validação executada pela IA: `pre-commit run --all-files` passou sem alterar nenhum arquivo, e o `pytest` deu **305 passed**. No clone descartável, o `git commit` foi barrado com erro corrigível de lint e de formatação, com nome indefinido, com `.env` adicionado à força e com `uv.lock` desatualizado. Depois da correção automática, o novo commit passou. A detecção de chave privada foi testada com `pre-commit run`, sem commit.

## MCP — ponte única

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A configuração do MCP com `docker run` criava um container por sessão do Claude Code, e a IA não avisou. | O responsável viu 6 containers no Docker Desktop e perguntou o motivo. | Um único container no `docker-compose.yml` (D-076). |
| Ao inspecionar o `.env`, a IA mascarou só as chaves com `PASSWORD` no nome, e a senha local dentro da `DATABASE_URL` apareceu na saída do comando. | A própria IA viu a saída. | Avisou o responsável. A senha não foi para o repositório, e a troca é decisão dele. |

Validação executada pela IA: dois clientes ao mesmo tempo na ponte leram `gold.pais_ano` (5.425 linhas cada), o `create table` foi recusado nos dois, e a tabela não existe no banco. O `docker compose up` não recriou o banco. Com o `.env.example`, como no CI, o Compose lista só o serviço `postgres`.

## Fase 7 — dashboards (Streamlit)

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A IA considerou o Streamlit pronto porque os testes das páginas passavam, mas o ranking quebrava no navegador: o teste roda o Python, e não desenha o gráfico. | Abrindo a tela em um navegador de verdade. | O gráfico foi reescrito como uma só visão, e cada tela foi conferida por imagem. O CI continua sem desenhar os gráficos. |
| Um texto com dois `$` virou fórmula matemática na tela. | Na conferência visual. | Uma função protege o `$` nos textos dinâmicos. |
| O quarto cartão da reconciliação mostrava o ano, e não o desvio do mundo do desenho aprovado. | Comparando a tela com o desenho. | A consulta passou a trazer o valor, e o cartão segue o desenho. |
| A IA deixou os nomes em inglês por entender que o dado devia aparecer como veio da API, e avisou só como detalhe. | O responsável pediu tudo em português, com termos financeiros. | Tradução em `silver.nome_portugues`, usada pela gold (D-082). |
| A IA não previu o tamanho do limite do Figma no plano gratuito. Ele chegou depois do layout pronto, e a edição seguinte foi bloqueada. | O Figma recusou a chamada. | As imagens do layout ficaram no repositório. Os nomes novos aparecem nas imagens das telas reais. |
| A IA tirou várias capturas de tela ao mesmo tempo e viu imagens em branco, que pareciam um erro do dashboard. | O conteúdo da página estava certo, e o tamanho dos arquivos não batia. | As capturas passaram a ser feitas uma de cada vez, depois de a tela desenhar. |
| O plano pôs o modelo estrela na silver, sem motivo escrito, e a IA seguiu esse caminho por 6 fases sem questionar. | O responsável perguntou por que as dims não estavam na gold. | Silver só trata, e a estrela foi para a gold (D-087). A impressão digital das tabelas de consumo provou que nenhum número mudou. |
| A IA ia repetir no Power BI contas que estavam na consulta do Streamlit. | Ao planejar o modelo do Power BI contra a D-078. | As contas foram para `gold.resumo_anual` (D-085). |
| A IA usou `axisScale` para a escala logarítmica. O nome estava errado, e nem o esquema oficial nem o Desktop avisaram: ele só descartou a propriedade ao salvar. | Olhando a tela com dados, e comparando o que foi gerado com o que o Desktop salvou. | O nome certo é `logAxisScale`. A comparação achou só essa propriedade descartada. |
| A IA supôs que a coluna de ordem poria o Brasil à frente das bolhas. Ela só ordena a legenda. | Na conferência visual. | As bolhas ficaram menores, e o limite foi registrado na D-086. |
| A IA demorou a suspeitar que a senha estava sendo copiada da linha do outro usuário (`wb`). | O responsável disse que a senha continuava com 32 caracteres, o tamanho da senha do `wb`. | Depois de trocar a senha do `dashboard_leitor`, o login funcionou copiando da linha certa. |
| A IA disse que o Figma estava bloqueado e propôs importar à mão ou pagar um plano, sem antes ler a regra de limites. | O responsável desconfiou da ferramenta usada. A regra mostrou 20 chamadas por mês e uma ferramenta de escrita isenta. | O fundo foi enviado pela ferramenta isenta, sem custo. |

Validação executada pela IA no Power BI: cartões, títulos, Top 10 e ranking comparados com o banco e com o Streamlit, em 2023/2024 e com 2010 e Sul da Ásia pré-selecionados.

Validação executada pela IA: as 2 telas finais conferidas no navegador, e os números principais comparados com `select` direto na gold nos testes das páginas. O `dashboard_leitor` leu a gold, foi recusado em `silver`, `bronze`, `etl` e em escritas, e a permissão continuou depois de recriar as views. Os testes unitários e de integração, o Ruff e o pre-commit passaram.

## Fase 8 — Documentação

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| A primeira versão da spec montava o site em dois lugares: no CI e no workflow de publicação. | Ao escrever o workflow, depois que o responsável pediu a publicação. | O build ficou só no workflow de documentação, e a spec foi ajustada. |
| A IA supôs nomes de colunas ao consultar `etl.quality_check` e `gold.dim_indicador`, e usou `max` em uma coluna `uuid`, em vez de olhar o dicionário antes. | Erros do banco nas 3 consultas, que só liam dados. | As colunas foram lidas do catálogo, e os números da documentação vieram das consultas corrigidas. |
| Um comando com um `python` vazio no início travou o shell, e as edições seguintes do mesmo comando não rodaram. A IA viu o arquivo vazio de saída antes de perceber. | A spec continuava como rascunho depois do comando. | O comando foi parado, e as edições foram refeitas com a ferramenta de arquivos. |
| A documentação não dizia que a gold fica em **Materialized Views**. Sem isso, as dimensões parecem não estar na gold quando se olha a pasta **Tables** no DBeaver. | O responsável perguntou se as dims ainda estavam na silver. | A consulta ao catálogo confirmou as dims na gold, e o README e a página de Arquitetura passaram a explicar onde achá-las. |
| A IA explicou essa dúvida só pela pasta do DBeaver, e a explicação estava incompleta: as dims também não apareciam em **Materialized Views**, onde o DBeaver mostrava só 5 das 16 tabelas. A lista batia com a da Fase 6, o que aponta para uma lista antiga na memória do programa. | Print do DBeaver enviado pelo responsável, e consulta pelo mesmo endereço, que mostrou as 16. | A página de Arquitetura passou a indicar o **F5**. |

Validação executada pela IA: `ruff format --check`, `ruff check` e o pre-commit passaram, o `pytest` deu **429 passed** com cobertura de **99,58%**, o `pytest -m integration` deu **66 passed**, e `mkdocs build --strict` passou. Páginas de Arquitetura, Decisões e Dashboards conferidas no navegador. Os avisos citados em `docs/quality.md` foram comparados com `etl.quality_check`, e o comando de conferência de `docs/installation.md` foi executado.

## Fase 9 — Validação final

| O que a IA assumiu ou errou | Como foi descoberto | Correção |
|---|---|---|
| Ao religar o banco depois da replicação, o script ainda tinha o nome do projeto de teste ativo. O Docker subiu um banco **vazio e novo** no lugar do banco original, e o volume original ficou desligado. | A conferência final do próprio script acusou diferença, com falha de senha. A IA conferiu qual volume estava em uso antes de mexer em qualquer coisa. | O banco vazio foi removido, e o original foi religado. As 16 tabelas ficaram idênticas às de antes do teste, e nenhum dado se perdeu. |
| A varredura de segredos voltou vazia porque o `gitleaks` nem rodou: o Git Bash trocou o caminho da pasta. Vazio não era prova de limpeza. | A IA desconfiou da saída vazia e repetiu o comando mostrando a saída inteira. | Rodou de novo com o caminho certo: 24 commits varridos e nenhum segredo. |
| O teste de senha nos erros parecia aprovado com "0 senhas", mas o comando tinha sido cortado pelo limite de tempo, antes de dar erro. | A saída tinha uma única linha, e a IA conferiu o código de saída: 124. | O teste revelou uma espera silenciosa de 130 segundos na conexão, corrigida na D-093. Repetido, ele terminou com erro em 11 segundos e sem a senha na mensagem. |
| Um comando com um `python` vazio no início travou o shell por mais de 8 minutos. **É o mesmo erro da Fase 8**, repetido. | O responsável perguntou se tinha travado. A saída estava vazia, e a lista de processos mostrou o `python` parado. | O bloco foi encerrado e rodado de novo sem esse comando, com limite de tempo e entrada fechada em cada passo. |
| A IA rodou os testes de integração com um comando diferente do documentado, e viu 7 testes pulados e erro de cobertura. | A própria saída, comparada com o README. | Não havia defeito: com o comando do README, os 66 passam. |
| O plano tratava `.pbix` como requisito, mas essa foi uma escolha da IA ao escrever o plano. | Ao montar a tabela de requisitos, a IA perguntou ao responsável, que confirmou que o dashboard é opcional. | Registrado na D-094. |
| A IA supôs o nome das colunas de `etl.quality_check` em uma consulta final do script, sem olhar o dicionário. **É o mesmo erro da Fase 8.** | Erro do banco. | Sem efeito no resultado: as regras reprovadas já estavam na mensagem do `run-all`. |
| O `pandas` ficou nas dependências do pipeline sem nenhum uso, desde o plano inicial. | Varredura da Fase 9, buscando cada dependência no código. | Removido com a aprovação do responsável. Os testes passaram sem ele. |
| O comando de conferência em `docs/installation.md` usava aspas simples, escritas para o Git Bash, sem teste no Prompt de Comando do Windows. | Leitura do comando na limpeza dos textos. | Trocado por um comando mais simples, testado nos dois terminais. |
| A IA marcou como cumprido o requisito "dashboard sem cálculo na tela", mas a tela ainda convertia o PIB para bilhões, calculava o top 10, o líder e o destaque do Brasil, e o Power BI somava valores nos gráficos. A conversão estava registrada na D-086 como exceção, e a IA aceitou a própria exceção sem comparar com a letra do requisito. | O responsável colou o enunciado do curso, e a IA conferiu cada item contra o texto original, procurando conta no código das telas. | Tudo passou para a gold (D-097). As colunas antigas e as outras 14 tabelas ficaram idênticas, as telas do Streamlit iguais às imagens, e três testes novos recusam conta na tela. |
| Um comando com um `python3` vazio no início travou de novo. **É a terceira vez** que esse erro acontece (Fases 8 e 9). | A saída não chegou, e o comando foi para o segundo plano. | Encerrado e rodado sem a linha. Regra para a IA: nunca começar um comando com um interpretador sem arquivo ou entrada. |
| A IA fez commit e push com um teste falhando. O teste não reconhecia nome de medida sem aspas, como o Power BI Desktop grava ao salvar o projeto, e a IA não parou quando a conferência mostrou a falha. No mesmo comando, deu duas entradas ao `python`, e a edição que separaria os commits não rodou. | A saída do próprio comando, lida depois do push. | O teste passou a aceitar os dois formatos, em um commit de correção. Regra para a IA: commit só depois de ler o resultado dos testes, em um comando separado. |

Validação executada pela IA, em clone limpo e com banco vazio: 6 comandos do pipeline sem erro, 16 tabelas da gold idênticas às do banco original, **429 testes unitários** com cobertura de **99,59%**, **66 de integração**, e `run-all` idempotente. O relatório completo está em [Validação final](validacao-final.md).
