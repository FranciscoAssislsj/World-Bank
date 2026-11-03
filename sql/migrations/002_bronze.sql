-- 002_bronze.sql
-- bronze.api_response: uma linha = uma página de resposta da API, em uma carga.
-- O payload é guardado sem nenhuma alteração (D-008). A tabela é append-only,
-- garantido pelos triggers no fim do arquivo (D-009). Uma requisição só ganha
-- linhas novas quando o conteúdo mudou desde a última carga (D-010).

create table bronze.api_response (
    response_id  bigint generated always as identity primary key,
    run_id       uuid        not null,
    endpoint     text        not null,
    params       jsonb       not null,
    params_hash  text        not null,
    page         integer     not null check (page >= 1),
    pages        integer     not null check (pages >= 0),
    total        integer     not null check (total >= 0),
    record_count integer     not null check (record_count >= 0),
    payload      jsonb       not null,
    payload_hash text        not null,
    ingested_at  timestamptz not null default now(),
    constraint api_response_request_page_uq
        unique (endpoint, params_hash, page, ingested_at)
);

comment on table bronze.api_response is
    'Uma página de resposta da World Bank API v2, como veio. Append-only.';
comment on column bronze.api_response.params_hash is
    'SHA-256 de endpoint + params (sem page): identifica a requisição (D-012).';
comment on column bronze.api_response.payload_hash is
    'SHA-256 do payload: detecta se a página mudou desde a última carga (D-010).';

-- A silver e a comparação da D-010 buscam a carga mais recente de cada requisição.
create index api_response_latest_idx
    on bronze.api_response (params_hash, ingested_at desc);

-- Trava append-only (D-009): bloqueia UPDATE, DELETE e TRUNCATE.
create function bronze.reject_change() returns trigger
language plpgsql as $$
begin
    raise exception 'bronze.% é append-only: % não é permitido',
        tg_table_name, tg_op;
end;
$$;

create trigger api_response_no_update_delete
    before update or delete on bronze.api_response
    for each row execute function bronze.reject_change();

create trigger api_response_no_truncate
    before truncate on bronze.api_response
    for each statement execute function bronze.reject_change();
