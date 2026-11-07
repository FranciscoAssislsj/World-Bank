# Validação final

Esta página reúne as provas da entrega, conferidas em 2026-11-07. Cada linha diz o que foi verificado e qual foi o resultado.

## Requisitos da entrega

| Requisito | Onde é atendido | Como foi conferido |
|---|---|---|
| Fonte pública e licença | [World Bank API v2](data-sources.md), CC BY 4.0 no README | leitura do README |
| Pelo menos 2 tabelas com JOIN | `gold.pais_ano` e `gold.ranking_crescimento` juntam fatos e dimensões | [`20_pais_ano.sql`](https://github.com/FranciscoAssislsj/World-Bank/blob/main/sql/gold/20_pais_ano.sql) e consulta ao banco |
| 3 camadas separadas, com a bruta intacta | schemas `bronze`, `silver` e `gold`; gatilhos impedem alterar a bronze | migrações e busca no código: nenhum `UPDATE` ou `DELETE` na bronze |
| Testes com dado inventado, sem abrir o banco | `tests/`, fora de `tests/integration/` | 446 testes unitários na versão final, sem rede e sem banco |
| Repositório público, um commit por etapa | GitHub, merges sem squash | `gh repo view` e `git log` |
| Dashboards lendo só a gold, sem nenhum cálculo na tela | Streamlit e Power BI ([D-078 e D-097](data-decisions.md)) | permissões do `dashboard_leitor` e testes que recusam conta, agregação, soma automática e Top N; cada teste foi conferido com uma conta plantada de propósito |
| Power BI no repositório | projeto `.pbip`, PDF e imagens das telas ([D-094](data-decisions.md)) | teste do projeto e [página de dashboards](dashboards.md) |
| Seção "Onde a IA errou" | README e [registro completo](ai-log.md) | leitura |
| Um `.sql` por view da gold, com cabeçalho | `sql/gold/`, 16 arquivos e 16 tabelas no banco | teste do cabeçalho e impressão digital das 16 tabelas |
| Cada decisão com motivo | [Decisões](data-decisions.md) | script: nenhum número faltando, nenhuma decisão sem motivo, nenhuma citação a decisão inexistente |

## O banco é igual à fonte

Um script separado, sem usar o código do pipeline, baixou tudo de novo e comparou com a gold. Assim, um erro no pipeline não apareceria igual dos dois lados.

| O que foi comparado | Linhas | Diferenças |
|---|---|---|
| Observações: país, indicador, ano, valor exato e casas decimais | 99.750 (19.027 sem valor) | 0 |
| Países e agregados | 296 | 0 |
| Indicadores e ligações com temas | 15 e 23 | 0 |
| Regiões, níveis de renda e tipos de empréstimo | 44, 7 e 4 | 0 |
| Fontes e temas | 71 e 21 | 0 |
| Histórico de renda, contra o arquivo oficial | 7.990 | 0 |
| `gold.pais_ano`: população, expectativa de vida, PIB e PIB per capita | 5.425 | 0 |

O crescimento do PIB e da população urbana em `gold.ranking_crescimento` também foi recalculado por fora para Brasil, China e África do Sul, e bateu até a 6ª casa decimal.

"Igual" significa fiel à API, sem comparar com outras fontes ([D-070](data-decisions.md)). Os valores estranhos da própria fonte estão em [Qualidade dos dados](quality.md).

## Replicação do zero

Um clone limpo, sem `.env`, sem `.venv` e com um banco vazio, seguiu os comandos do README.

| Conferência | Resultado |
|---|---|
| `uv sync`, `.env` copiado do exemplo, sem nenhum ajuste, e `docker compose up` | funcionou |
| Os 6 comandos do pipeline, na ordem do README | todos sem erro |
| As 16 tabelas da gold, contra o banco original | idênticas |
| Lint, formatação e `mkdocs build --strict` | sem erro |
| Testes unitários e de integração | 429 e 66 passaram, nenhum pulado |
| Streamlit | servidor no ar, respondendo |
| `run-all` duas vezes | gold idêntica e nenhuma página nova na bronze |
| Um percentual de 150 plantado na silver | `run-all` falhou nas regras `faixa_percentual` e `fato_diverge_bronze`, e a gold não mudou |

**Limites:**

- Depois do teste, mudaram textos da documentação, a descrição do `pyproject.toml` e a dependência `pandas`, que nada usava; os comandos do README não mudaram, e todos os testes rodaram de novo. Os testes da documentação cresceram com essas páginas, de 429 para 431.
- O teste foi na mesma máquina Windows, com Docker e `uv` já instalados. O [CI](development.md#ci) cobre uma máquina Linux limpa.
- O Power BI Desktop não roda de forma automática. O projeto tem um teste próprio, e o responsável abriu o relatório no Desktop e atualizou os dados em 2026-11-07, sem erro.
- Quem fez o teste foi a própria IA, que conhece o projeto. Uma pessoa de fora ainda pode encontrar outra dificuldade.

## Segurança

| Conferência | Resultado |
|---|---|
| Segredos em todo o histórico, com `gitleaks` | nenhum |
| Senhas locais no histórico do git | nenhuma |
| Arquivos públicos | sem `.env`, cache do Power BI ou caminho da máquina |
| Imagens das telas | conferidas uma a uma, só com dados públicos do World Bank |
| Metadados do PDF | sem nome de pessoa nem caminho |
| Rede | banco e ponte MCP aceitam conexão só da própria máquina |
| `dashboard_leitor` | lê só a gold, e não tem permissão de escrita em nenhuma tabela |
| Ponte MCP | recusou o comando de escrita testado |
| Workflows | leitura por padrão; escrita só na etapa que publica o site |
| Dependências, com `pip-audit` | nenhuma vulnerabilidade conhecida |
| Erro de conexão | a senha não aparece na mensagem |

**Limite:** o usuário `wb` do pipeline é administrador do banco, como é padrão na imagem do PostgreSQL. Para este projeto local, o risco é baixo. Em produção, o pipeline precisaria de um usuário com menos poderes.

## Boas práticas

| Conferência | Resultado |
|---|---|
| `uv sync --locked`, Ruff e pre-commit | sem erro |
| CI e publicação do site na `main` | verdes |
| Versões das ações do GitHub | fixadas por hash |
| `print` no código ou `except` que esconde erro | nenhum |
| Dependências sem uso | `pandas` removido das dependências do pipeline; o Streamlit instala a versão de que precisa |

**Correção feita nesta validação:** com o banco desligado, um comando ficava parado em silêncio por mais de 100 segundos. Agora ele avisa em cerca de 10 segundos ([D-093](data-decisions.md)).
