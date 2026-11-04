-- 007_quality_check.sql
-- etl.quality_check: o resultado de cada regra de sql/quality/ em cada execução (D-054).

create table etl.quality_check (
    check_id    bigint generated always as identity primary key,
    run_id      uuid        not null references etl.pipeline_run on delete cascade,
    check_name  text        not null,
    severity    text        not null check (severity in ('error', 'warning')),
    passed      boolean     not null,
    rows_failed integer     not null check (rows_failed >= 0),
    sample      jsonb       not null,
    checked_at  timestamptz not null default now()
);

create index quality_check_run_idx on etl.quality_check (run_id);

comment on table etl.quality_check is
    'Uma linha = o resultado de uma regra de qualidade em uma execução (D-054).';
comment on column etl.quality_check.check_id is 'Identificador da linha.';
comment on column etl.quality_check.run_id is 'Execução que rodou a regra.';
comment on column etl.quality_check.check_name is 'Nome do arquivo em sql/quality/, sem .sql.';
comment on column etl.quality_check.severity is
    'error bloqueia; warning só registra (D-051).';
comment on column etl.quality_check.passed is 'true quando não há linhas com problema.';
comment on column etl.quality_check.rows_failed is 'Linhas com problema.';
comment on column etl.quality_check.sample is 'Até 5 exemplos das linhas com problema.';
comment on column etl.quality_check.checked_at is 'Quando o resultado foi gravado.';
