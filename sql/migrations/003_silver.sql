-- 003_silver.sql
-- Dimensões da silver: cadastros da API limpos, tipados e ligados por chaves.
-- Os nomes são em português (D-015). As restrições ficam também no banco para
-- valer em qualquer escrita (D-028). bronze_run_id e atualizado_em são a
-- linhagem de cada linha (D-033), e os comentários são o dicionário de dados (D-035).

create table silver.dim_regiao (
    regiao_id     text        primary key,
    regiao_iso2   text        not null unique,
    nome          text        not null,
    e_geografica  boolean     not null,
    bronze_run_id uuid        not null,
    atualizado_em timestamptz not null default now()
);

comment on table silver.dim_regiao is
    'Uma linha = uma região geográfica ou um agrupamento de países.';
comment on column silver.dim_regiao.regiao_id is
    'Código da região (campo code da API, D-016).';
comment on column silver.dim_regiao.regiao_iso2 is 'Código de 2 caracteres da API.';
comment on column silver.dim_regiao.nome is 'Nome da região, como veio da API.';
comment on column silver.dim_regiao.e_geografica is
    'true nas 7 regiões geográficas; false nos agrupamentos, que se sobrepõem (D-016).';
comment on column silver.dim_regiao.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_regiao.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_nivel_renda (
    nivel_renda_id   text        primary key,
    nivel_renda_iso2 text        not null unique,
    nome             text        not null,
    ordem            smallint    check (ordem between 1 and 4),
    e_agrupamento    boolean     not null,
    bronze_run_id    uuid        not null,
    atualizado_em    timestamptz not null default now()
);

comment on table silver.dim_nivel_renda is
    'Uma linha = um nível de renda ou um agrupamento de níveis.';
comment on column silver.dim_nivel_renda.nivel_renda_id is 'Código do nível (ex.: HIC).';
comment on column silver.dim_nivel_renda.nivel_renda_iso2 is
    'Código de 2 caracteres da API.';
comment on column silver.dim_nivel_renda.nome is 'Nome do nível, como veio da API.';
comment on column silver.dim_nivel_renda.ordem is
    'Sequência para ordenar: 1 = baixa, 2 = média-baixa, 3 = média-alta, 4 = alta; NULL nos demais (D-034).';
comment on column silver.dim_nivel_renda.e_agrupamento is
    'true em LMY e MIC, que somam outros níveis: não somar junto com eles (D-034).';
comment on column silver.dim_nivel_renda.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_nivel_renda.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_tipo_emprestimo (
    tipo_emprestimo_id   text        primary key,
    tipo_emprestimo_iso2 text        not null unique,
    nome                 text        not null,
    bronze_run_id        uuid        not null,
    atualizado_em        timestamptz not null default now()
);

comment on table silver.dim_tipo_emprestimo is
    'Uma linha = um tipo de empréstimo do World Bank.';
comment on column silver.dim_tipo_emprestimo.tipo_emprestimo_id is
    'Código do tipo (ex.: IBD).';
comment on column silver.dim_tipo_emprestimo.tipo_emprestimo_iso2 is
    'Código de 2 caracteres da API.';
comment on column silver.dim_tipo_emprestimo.nome is 'Nome do tipo, como veio da API.';
comment on column silver.dim_tipo_emprestimo.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_tipo_emprestimo.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_fonte (
    fonte_id           integer     primary key,
    codigo             text        not null unique,
    nome               text        not null,
    conceitos          integer     not null check (conceitos >= 0),
    ultima_atualizacao date        not null,
    tem_dados          boolean     not null,
    tem_metadados      boolean,
    bronze_run_id      uuid        not null,
    atualizado_em      timestamptz not null default now()
);

comment on table silver.dim_fonte is 'Uma linha = uma base de dados do World Bank.';
comment on column silver.dim_fonte.fonte_id is 'Identificador da fonte (ex.: 2 = WDI).';
comment on column silver.dim_fonte.codigo is 'Código curto da fonte (ex.: WDI).';
comment on column silver.dim_fonte.nome is 'Nome da fonte, como veio da API.';
comment on column silver.dim_fonte.conceitos is 'Número de conceitos informado pela API.';
comment on column silver.dim_fonte.ultima_atualizacao is
    'Data da última atualização da fonte, segundo a API.';
comment on column silver.dim_fonte.tem_dados is 'A fonte tem dados disponíveis.';
comment on column silver.dim_fonte.tem_metadados is
    'A fonte tem metadados; NULL quando a API não informa (D-027).';
comment on column silver.dim_fonte.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_fonte.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_topico (
    topico_id     integer     primary key,
    nome          text        not null,
    descricao     text,
    bronze_run_id uuid        not null,
    atualizado_em timestamptz not null default now()
);

comment on table silver.dim_topico is 'Uma linha = um tema dos indicadores.';
comment on column silver.dim_topico.topico_id is 'Identificador do tópico.';
comment on column silver.dim_topico.nome is 'Nome do tópico, como veio da API.';
comment on column silver.dim_topico.descricao is 'Descrição do tópico; NULL se vazia.';
comment on column silver.dim_topico.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_topico.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_pais (
    pais_iso3                text        primary key,
    pais_iso2                text        not null unique,
    nome                     text        not null,
    regiao_id                text        references silver.dim_regiao,
    nivel_renda_atual_id     text        references silver.dim_nivel_renda,
    tipo_emprestimo_atual_id text        references silver.dim_tipo_emprestimo,
    regiao_administrativa_id text        references silver.dim_regiao,
    capital                  text,
    latitude                 numeric     check (latitude between -90 and 90),
    longitude                numeric     check (longitude between -180 and 180),
    e_agregado               boolean     not null,
    tipo_agregado            text
        check (tipo_agregado in ('regiao', 'renda', 'tipo_emprestimo', 'outro')),
    bronze_run_id            uuid        not null,
    atualizado_em            timestamptz not null default now(),
    -- D-028: se a fonte mudar esse formato, a carga falha em vez de gravar errado.
    constraint dim_pais_agregado_ck check (
        (
            e_agregado
            and regiao_id is null
            and nivel_renda_atual_id is null
            and tipo_emprestimo_atual_id is null
            and tipo_agregado is not null
        )
        or (
            not e_agregado
            and regiao_id is not null
            and nivel_renda_atual_id is not null
            and tipo_emprestimo_atual_id is not null
            and tipo_agregado is null
        )
    )
);

comment on table silver.dim_pais is
    'Uma linha = um país ou um agregado. Filtre e_agregado para não somar os dois (D-023).';
comment on column silver.dim_pais.pais_iso3 is 'Código de 3 caracteres (campo id da API).';
comment on column silver.dim_pais.pais_iso2 is
    'Código de 2 caracteres; liga as observações sem ISO3 (Fase 4).';
comment on column silver.dim_pais.nome is 'Nome do país ou agregado, como veio da API.';
comment on column silver.dim_pais.regiao_id is
    'Região geográfica; NULL em agregados (D-017).';
comment on column silver.dim_pais.nivel_renda_atual_id is
    'Classificação de renda ATUAL, não a de cada ano; NULL em agregados (D-017, D-025).';
comment on column silver.dim_pais.tipo_emprestimo_atual_id is
    'Tipo de empréstimo ATUAL, não o de cada ano; NULL em agregados (D-017, D-025).';
comment on column silver.dim_pais.regiao_administrativa_id is
    'Região sem os países de renda alta; NULL nos demais casos (D-034).';
comment on column silver.dim_pais.capital is 'Capital; NULL se a API não informa.';
comment on column silver.dim_pais.latitude is 'Latitude; NULL se a API não informa.';
comment on column silver.dim_pais.longitude is 'Longitude; NULL se a API não informa.';
comment on column silver.dim_pais.e_agregado is
    'true quando a linha é um agregado, e não um país (D-017).';
comment on column silver.dim_pais.tipo_agregado is
    'Em agregados: regiao, renda, tipo_emprestimo ou outro; NULL em países (D-034).';
comment on column silver.dim_pais.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_pais.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.dim_indicador (
    indicador_id      text        primary key,
    nome              text        not null,
    fonte_id          integer     not null references silver.dim_fonte,
    descricao         text,
    organizacao_fonte text,
    bronze_run_id     uuid        not null,
    atualizado_em     timestamptz not null default now()
);

comment on table silver.dim_indicador is
    'Uma linha = uma série de dados. Só os indicadores configurados (D-022).';
comment on column silver.dim_indicador.indicador_id is
    'Código do indicador (ex.: SP.POP.TOTL).';
comment on column silver.dim_indicador.nome is 'Nome do indicador, como veio da API.';
comment on column silver.dim_indicador.fonte_id is 'Fonte do indicador.';
comment on column silver.dim_indicador.descricao is 'Descrição; NULL se vazia.';
comment on column silver.dim_indicador.organizacao_fonte is
    'Organização que produz o dado; NULL se vazia.';
comment on column silver.dim_indicador.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.dim_indicador.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table silver.ponte_indicador_topico (
    indicador_id  text        not null references silver.dim_indicador,
    topico_id     integer     not null references silver.dim_topico,
    bronze_run_id uuid        not null,
    atualizado_em timestamptz not null default now(),
    primary key (indicador_id, topico_id)
);

comment on table silver.ponte_indicador_topico is
    'Uma linha = a ligação de um indicador a um tópico (N:N, D-026).';
comment on column silver.ponte_indicador_topico.indicador_id is 'Indicador ligado.';
comment on column silver.ponte_indicador_topico.topico_id is 'Tópico ligado.';
comment on column silver.ponte_indicador_topico.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.ponte_indicador_topico.atualizado_em is
    'Quando a ligação foi criada (D-033).';
