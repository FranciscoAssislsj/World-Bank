-- 004_renda_historica.sql
-- Histórico oficial da classificação de renda (OGHIST), um Excel fora da API.
-- bronze.source_file guarda o arquivo original, sem alteração (D-036).
-- silver.classificacao_renda_anual tem uma linha por país e ano (D-038).

create table bronze.source_file (
    file_id      bigint generated always as identity primary key,
    run_id       uuid        not null,
    source       text        not null,
    url          text        not null,
    content      bytea       not null,
    content_hash text        not null,
    size_bytes   integer     not null check (size_bytes > 0),
    ingested_at  timestamptz not null default now()
);

comment on table bronze.source_file is
    'Uma linha = uma versão de um arquivo baixado fora da API, como veio. Append-only.';
comment on column bronze.source_file.source is
    'Identifica o arquivo (ex.: income_history).';
comment on column bronze.source_file.url is 'Endereço de onde o arquivo foi baixado.';
comment on column bronze.source_file.content is 'Bytes do arquivo, sem alteração.';
comment on column bronze.source_file.content_hash is
    'SHA-256 do conteúdo: detecta se o arquivo mudou desde a última carga.';

create index source_file_latest_idx
    on bronze.source_file (source, ingested_at desc);

-- Mesma trava append-only de bronze.api_response (D-009).
create trigger source_file_no_update_delete
    before update or delete on bronze.source_file
    for each row execute function bronze.reject_change();

create trigger source_file_no_truncate
    before truncate on bronze.source_file
    for each statement execute function bronze.reject_change();

create table silver.classificacao_renda_anual (
    pais_iso3      text        not null references silver.dim_pais,
    ano_referencia smallint    not null,
    ano_fiscal     smallint    not null,
    nivel_renda_id text        not null references silver.dim_nivel_renda,
    bronze_run_id  uuid        not null,
    atualizado_em  timestamptz not null default now(),
    primary key (pais_iso3, ano_referencia),
    constraint classificacao_renda_anual_ano_ck
        check (ano_fiscal = ano_referencia + 2)
);

comment on table silver.classificacao_renda_anual is
    'Uma linha = a classificação oficial de renda de um país para um ano (D-038).';
comment on column silver.classificacao_renda_anual.pais_iso3 is 'País classificado.';
comment on column silver.classificacao_renda_anual.ano_referencia is
    'Ano da renda usada na classificação. É o ano para ligar às observações (D-038).';
comment on column silver.classificacao_renda_anual.ano_fiscal is
    'Ano fiscal do World Bank em que a classificação vigorou.';
comment on column silver.classificacao_renda_anual.nivel_renda_id is
    'Nível de renda do país naquele ano.';
comment on column silver.classificacao_renda_anual.bronze_run_id is
    'Carga da bronze de onde a linha veio (D-033).';
comment on column silver.classificacao_renda_anual.atualizado_em is
    'Quando a linha foi criada ou um valor mudou pela última vez (D-033).';
