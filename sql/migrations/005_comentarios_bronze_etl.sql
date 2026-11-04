-- 005_comentarios_bronze_etl.sql
-- Completa o dicionário de dados: as colunas de bronze e etl que ainda não tinham
-- descrição no banco (D-035). Não muda nenhum dado.

comment on column bronze.api_response.response_id is 'Identificador da linha.';
comment on column bronze.api_response.run_id is 'Execução do pipeline que gravou a página.';
comment on column bronze.api_response.endpoint is 'Caminho chamado na API (ex.: country).';
comment on column bronze.api_response.params is 'Parâmetros enviados na requisição, sem a página.';
comment on column bronze.api_response.page is 'Número da página na resposta.';
comment on column bronze.api_response.pages is 'Total de páginas informado pela API.';
comment on column bronze.api_response.total is 'Total de registros informado pela API.';
comment on column bronze.api_response.record_count is 'Registros contados nesta página.';
comment on column bronze.api_response.payload is 'Resposta da API, sem alteração (D-008).';
comment on column bronze.api_response.ingested_at is 'Quando a página foi gravada.';

comment on column bronze.source_file.file_id is 'Identificador da linha.';
comment on column bronze.source_file.run_id is 'Execução do pipeline que gravou o arquivo.';
comment on column bronze.source_file.size_bytes is 'Tamanho do arquivo, em bytes.';
comment on column bronze.source_file.ingested_at is 'Quando o arquivo foi gravado.';

comment on table etl.schema_migrations is
    'Uma linha = uma migração de sql/migrations/ já aplicada.';
comment on column etl.schema_migrations.version is 'Número da migração (ex.: 003).';
comment on column etl.schema_migrations.filename is 'Nome do arquivo da migração.';
comment on column etl.schema_migrations.checksum is
    'SHA-256 do arquivo: detecta edição depois de aplicada.';
comment on column etl.schema_migrations.applied_at is 'Quando a migração foi aplicada.';
