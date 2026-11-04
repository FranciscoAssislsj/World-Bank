-- 006_fato_observacao.sql
-- silver.fato_observacao: os valores dos indicadores, com grão país + indicador + ano
-- (D-040). etl.pipeline_run: o registro de cada execução do pipeline (D-046).

create table silver.fato_observacao (
    pais_iso3      text        not null references silver.dim_pais,
    indicador_id   text        not null references silver.dim_indicador,
    ano            smallint    not null,
    valor          numeric,
    casas_decimais smallint    not null check (casas_decimais >= 0),
    bronze_run_id  uuid        not null,
    atualizado_em  timestamptz not null default now(),
    primary key (pais_iso3, indicador_id, ano)
);

-- A chave primária começa por país; consultas por indicador usam este índice (D-048).
create index fato_observacao_indicador_ano_idx
    on silver.fato_observacao (indicador_id, ano);

comment on table silver.fato_observacao is
    'Uma linha = o valor de um indicador para um país ou agregado em um ano. Filtre dim_pais.e_agregado para não somar os dois (D-040).';
comment on column silver.fato_observacao.pais_iso3 is 'País ou agregado medido (D-041).';
comment on column silver.fato_observacao.indicador_id is 'Indicador medido.';
comment on column silver.fato_observacao.ano is 'Ano da observação.';
comment on column silver.fato_observacao.valor is
    'Valor medido, sem arredondamento; NULL quando a fonte não tem o dado (D-042, D-043).';
comment on column silver.fato_observacao.casas_decimais is
    'Casas sugeridas pela API para exibir o valor; não altera o valor guardado (D-047).';
comment on column silver.fato_observacao.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.fato_observacao.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';

create table etl.pipeline_run (
    run_id         uuid        primary key,
    pipeline       text        not null,
    params         jsonb       not null,
    bronze_run_ids uuid[]      not null default '{}',
    status         text        not null
        check (status in ('running', 'success', 'skipped', 'failed')),
    rows_read      integer     check (rows_read >= 0),
    rows_written   integer     check (rows_written >= 0),
    error_message  text,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz
);

-- A execução incremental procura a última execução bem-sucedida do comando (D-045).
create index pipeline_run_latest_idx
    on etl.pipeline_run (pipeline, started_at desc);

comment on table etl.pipeline_run is
    'Uma linha = uma execução de um comando do pipeline (D-046).';
comment on column etl.pipeline_run.run_id is 'Identificador da execução.';
comment on column etl.pipeline_run.pipeline is 'Comando executado (ex.: load-observations).';
comment on column etl.pipeline_run.params is 'Período e indicadores usados.';
comment on column etl.pipeline_run.bronze_run_ids is
    'Cargas da bronze lidas, em ordem; vazio se falhou antes de ler (D-045).';
comment on column etl.pipeline_run.status is 'running, success, skipped ou failed.';
comment on column etl.pipeline_run.rows_read is 'Linhas lidas da bronze.';
comment on column etl.pipeline_run.rows_written is 'Linhas inseridas ou alteradas.';
comment on column etl.pipeline_run.error_message is 'Mensagem de erro; só em falha.';
comment on column etl.pipeline_run.started_at is 'Início da execução.';
comment on column etl.pipeline_run.finished_at is 'Fim da execução; NULL enquanto roda.';
