"""Acesso ao PostgreSQL: conexão, migrações, gravação na bronze e upsert na silver.

As migrações são arquivos ``sql/migrations/NNN_nome.sql`` aplicados em ordem.
Cada uma aplicada fica registrada em ``etl.schema_migrations`` com o checksum
do arquivo, para não rodar de novo e para detectar edição depois de aplicada.
"""

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from world_bank.config import Settings
from world_bank.exceptions import LoadError, MigrationError
from world_bank.extract.client import ApiPage

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "sql" / "migrations"

_MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")

# Linhagem (D-033): não conta como mudança de valor no upsert.
_LINEAGE_COLUMN = "bronze_run_id"

# Criada aqui, e não numa migração, porque o migrate precisa dela para saber
# quais migrações já rodaram.
_BOOTSTRAP_SQL = """
create schema if not exists etl;
create table if not exists etl.schema_migrations (
    version    text        primary key,
    filename   text        not null,
    checksum   text        not null,
    applied_at timestamptz not null default now()
);
"""


@dataclass(frozen=True)
class Migration:
    """Um arquivo de migração lido do disco.

    Attributes:
        version: Prefixo numérico do arquivo (ex.: ``"001"``).
        filename: Nome do arquivo (ex.: ``"001_schemas.sql"``).
        sql: Conteúdo do arquivo.
        checksum: SHA-256 do conteúdo, com quebras de linha normalizadas.
    """

    version: str
    filename: str
    sql: str
    checksum: str


@dataclass(frozen=True)
class BronzeLoad:
    """A carga mais recente de um endpoint na bronze.

    Attributes:
        endpoint: Caminho do endpoint (ex.: ``"country"``).
        run_id: Execução que gravou a carga.
        records: Registros de todas as páginas, na ordem.
    """

    endpoint: str
    run_id: UUID
    records: list[dict[str, Any]]


@dataclass(frozen=True)
class SourceFile:
    """Um arquivo baixado fora da API e guardado na bronze.

    Attributes:
        source: Identificador do arquivo (ex.: ``"income_history"``).
        run_id: Execução que gravou o arquivo.
        content: Bytes do arquivo.
        content_hash: SHA-256 do conteúdo.
    """

    source: str
    run_id: UUID
    content: bytes
    content_hash: str


def connect(settings: Settings) -> psycopg.Connection:
    """Abre uma conexão com o banco em modo autocommit.

    Com autocommit, cada ``conn.transaction()`` é uma transação real, e não um
    savepoint dentro de uma transação implícita.

    Args:
        settings: Configurações com ``DATABASE_URL``.

    Returns:
        Conexão aberta. Use como context manager para fechá-la.

    Raises:
        LoadError: Se não for possível conectar (banco desligado, senha errada).
    """
    try:
        return psycopg.connect(
            settings.database_url.get_secret_value(), autocommit=True
        )
    except psycopg.OperationalError as exc:
        raise LoadError(f"não foi possível conectar ao banco: {exc}") from exc


def checksum(sql: str) -> str:
    """Calcula o SHA-256 de um SQL, ignorando a diferença entre CRLF e LF.

    Sem a normalização, o mesmo arquivo teria checksum diferente no Windows
    (CRLF) e no Linux (LF), e o migrate acusaria uma edição que não houve.

    Args:
        sql: Conteúdo do arquivo.

    Returns:
        Hash em hexadecimal.
    """
    return hashlib.sha256(sql.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def list_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Lê as migrações do diretório, em ordem de versão.

    Args:
        directory: Diretório com os arquivos ``NNN_nome.sql``.

    Returns:
        Migrações ordenadas pela versão.

    Raises:
        MigrationError: Se algum ``.sql`` estiver fora do padrão de nome ou se
            duas migrações tiverem a mesma versão.
    """
    migrations: dict[str, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = _MIGRATION_NAME.match(path.name)
        if match is None:
            raise MigrationError(
                f"nome de migração fora do padrão NNN_nome.sql: {path.name}"
            )
        version = match["version"]
        if version in migrations:
            previous = migrations[version].filename
            msg = f"versão {version} repetida: {previous} e {path.name}"
            raise MigrationError(msg)
        sql = path.read_text(encoding="utf-8")
        migrations[version] = Migration(version, path.name, sql, checksum(sql))
    return [migrations[version] for version in sorted(migrations)]


def apply_migrations(
    conn: psycopg.Connection, migrations: list[Migration]
) -> list[Migration]:
    """Aplica, em ordem, as migrações que ainda não rodaram.

    Antes de aplicar qualquer uma, confere se as já aplicadas continuam iguais.
    Cada migração roda numa transação junto com o seu registro em
    ``etl.schema_migrations``: ou as duas coisas acontecem, ou nenhuma.

    Args:
        conn: Conexão em modo autocommit (ver ``connect``).
        migrations: Migrações lidas por ``list_migrations``.

    Returns:
        As migrações aplicadas nesta chamada (vazia se não havia nada novo).

    Raises:
        MigrationError: Se uma migração já aplicada foi alterada no disco ou se
            o SQL de uma migração falhar (ela é desfeita por inteiro).
    """
    with conn.transaction():
        conn.execute(_BOOTSTRAP_SQL)
    rows = conn.execute("select version, checksum from etl.schema_migrations")
    applied = dict(rows.fetchall())

    for migration in migrations:
        stored = applied.get(migration.version)
        if stored is not None and stored != migration.checksum:
            msg = (
                f"{migration.filename} foi alterada depois de aplicada; "
                "crie uma nova migração em vez de editar esta"
            )
            raise MigrationError(msg)

    pending = [m for m in migrations if m.version not in applied]
    for migration in pending:
        try:
            with conn.transaction():
                conn.execute(migration.sql)
                conn.execute(
                    "insert into etl.schema_migrations (version, filename, checksum)"
                    " values (%s, %s, %s)",
                    (migration.version, migration.filename, migration.checksum),
                )
        except psycopg.Error as exc:
            raise MigrationError(
                f"falha ao aplicar {migration.filename}: {exc}"
            ) from exc
        logger.info("migration applied", extra={"migration": migration.filename})
    return pending


def json_hash(value: Any) -> str:
    """Calcula o SHA-256 de um valor JSON, independente da ordem das chaves.

    Args:
        value: Qualquer valor serializável em JSON.

    Returns:
        Hash em hexadecimal.
    """
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_params(page: ApiPage) -> dict[str, str]:
    """Devolve os parâmetros da requisição sem o número da página.

    Args:
        page: Página extraída pelo cliente.

    Returns:
        Parâmetros enviados, sem ``page``.
    """
    return {key: value for key, value in page.params.items() if key != "page"}


def params_hash(page: ApiPage) -> str:
    """Identifica a requisição de uma página: endpoint + parâmetros, sem ``page``.

    Todas as páginas da mesma requisição têm o mesmo hash (D-012).

    Args:
        page: Página extraída pelo cliente.

    Returns:
        Hash em hexadecimal.
    """
    return json_hash({"endpoint": page.path, "params": request_params(page)})


def latest_payload_hashes(conn: psycopg.Connection, request_hash: str) -> list[str]:
    """Busca os ``payload_hash`` da carga mais recente de uma requisição.

    Args:
        conn: Conexão com o banco.
        request_hash: ``params_hash`` da requisição.

    Returns:
        Hashes das páginas, em ordem de página. Lista vazia se a requisição
        nunca foi gravada.
    """
    rows = conn.execute(
        """
        select payload_hash
        from bronze.api_response
        where params_hash = %(hash)s
          and ingested_at = (
              select max(ingested_at) from bronze.api_response
              where params_hash = %(hash)s
          )
        order by page
        """,
        {"hash": request_hash},
    )
    return [row[0] for row in rows.fetchall()]


def insert_pages(conn: psycopg.Connection, run_id: UUID, pages: list[ApiPage]) -> None:
    """Grava as páginas de uma requisição em ``bronze.api_response``.

    Só faz ``INSERT``: a tabela é append-only (D-009). Todas as linhas são
    gravadas na transação de quem chama e recebem o mesmo ``ingested_at``,
    porque ``now()`` é o horário de início da transação.

    Args:
        conn: Conexão com o banco, dentro de uma transação.
        run_id: Identificador da execução do pipeline.
        pages: Páginas da mesma requisição, na ordem.
    """
    rows = [
        (
            run_id,
            page.path,
            Jsonb(request_params(page)),
            params_hash(page),
            page.page,
            page.pages,
            page.total,
            len(page.records),
            Jsonb(page.payload),
            json_hash(page.payload),
        )
        for page in pages
    ]
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            insert into bronze.api_response (
                run_id, endpoint, params, params_hash, page, pages, total,
                record_count, payload, payload_hash
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )


def read_latest_load(conn: psycopg.Connection, endpoint: str) -> BronzeLoad | None:
    """Lê os registros da carga mais recente de um endpoint (D-013).

    Todas as páginas de uma carga têm o mesmo ``ingested_at``, porque são
    gravadas na mesma transação (D-011).

    Args:
        conn: Conexão com o banco.
        endpoint: Caminho do endpoint (ex.: ``"country"``).

    Returns:
        A carga, ou ``None`` se o endpoint nunca foi gravado.
    """
    rows = conn.execute(
        """
        select run_id, payload -> 1
        from bronze.api_response
        where endpoint = %(endpoint)s
          and ingested_at = (
              select max(ingested_at) from bronze.api_response
              where endpoint = %(endpoint)s
          )
        order by page
        """,
        {"endpoint": endpoint},
    ).fetchall()
    if not rows:
        return None
    records = [record for _, page_records in rows for record in page_records or []]
    return BronzeLoad(endpoint, rows[0][0], records)


def upsert_rows(
    conn: psycopg.Connection,
    table: str,
    key_columns: Sequence[str],
    rows: list[dict[str, Any]],
) -> int:
    """Insere ou atualiza linhas em ``silver.<table>`` (D-029).

    As linhas passam por uma tabela temporária com ``COPY`` e entram na definitiva
    com ``ON CONFLICT``. Uma linha existente só é regravada quando alguma coluna de
    dado mudou; ``bronze_run_id`` não conta como mudança (D-033). Nomes de tabela e
    de coluna entram como identificadores do SQL, nunca como texto concatenado.

    Args:
        conn: Conexão com o banco, dentro de uma transação.
        table: Nome da tabela no schema ``silver``.
        key_columns: Colunas da chave primária.
        rows: Linhas com as mesmas chaves em todos os dicionários.

    Returns:
        Número de linhas inseridas ou alteradas.
    """
    if not rows:
        return 0
    columns = list(rows[0])
    value_columns = [column for column in columns if column not in key_columns]
    data_columns = [column for column in value_columns if column != _LINEAGE_COLUMN]
    target = sql.Identifier("silver", table)
    staging = sql.Identifier(f"stg_{table}")
    column_list = _identifiers(columns)

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "create temp table {staging} (like {target} including defaults)"
                " on commit drop"
            ).format(staging=staging, target=target)
        )
        copy_sql = sql.SQL("copy {staging} ({columns}) from stdin").format(
            staging=staging, columns=column_list
        )
        with cursor.copy(copy_sql) as copy:
            for row in rows:
                copy.write_row([row[column] for column in columns])
        cursor.execute(
            sql.SQL(
                "insert into {target} as alvo ({columns})"
                " select {columns} from {staging} on conflict ({keys}) {action}"
            ).format(
                target=target,
                columns=column_list,
                staging=staging,
                keys=_identifiers(key_columns),
                action=_conflict_action(value_columns, data_columns),
            )
        )
        written = cursor.rowcount
        cursor.execute(sql.SQL("drop table {staging}").format(staging=staging))
    return written


def delete_missing_links(
    conn: psycopg.Connection,
    indicator_ids: Sequence[str],
    links: Sequence[tuple[str, int]],
) -> int:
    """Apaga da ponte as ligações que sumiram da fonte (D-030).

    Só olha os indicadores informados. As ligações que continuam na fonte não são
    tocadas, então mantêm o ``atualizado_em``.

    Args:
        conn: Conexão com o banco, dentro de uma transação.
        indicator_ids: Indicadores carregados.
        links: Pares ``(indicador_id, topico_id)`` que existem na fonte.

    Returns:
        Número de ligações apagadas.
    """
    cursor = conn.execute(
        """
        delete from silver.ponte_indicador_topico as alvo
        where alvo.indicador_id = any(%(indicators)s)
          and not exists (
              select 1
              from unnest(%(link_indicators)s::text[], %(link_topics)s::int[])
                  as fonte (indicador_id, topico_id)
              where fonte.indicador_id = alvo.indicador_id
                and fonte.topico_id = alvo.topico_id
          )
        """,
        {
            "indicators": list(indicator_ids),
            "link_indicators": [indicator for indicator, _ in links],
            "link_topics": [topic for _, topic in links],
        },
    )
    return cursor.rowcount


def _identifiers(names: Sequence[str]) -> sql.Composed:
    return sql.SQL(", ").join(map(sql.Identifier, names))


def _conflict_action(
    value_columns: Sequence[str], data_columns: Sequence[str]
) -> sql.Composable:
    """Monta o que fazer com uma chave que já existe na tabela."""
    if not data_columns:
        return sql.SQL("do nothing")
    assignments = [
        sql.SQL("{column} = excluded.{column}").format(column=sql.Identifier(column))
        for column in value_columns
    ]
    assignments.append(sql.SQL("atualizado_em = now()"))
    return sql.SQL(
        "do update set {assignments} where ({old}) is distinct from ({new})"
    ).format(
        assignments=sql.SQL(", ").join(assignments),
        old=sql.SQL(", ").join(sql.Identifier("alvo", c) for c in data_columns),
        new=sql.SQL(", ").join(sql.Identifier("excluded", c) for c in data_columns),
    )


def content_hash(content: bytes) -> str:
    """Calcula o SHA-256 dos bytes de um arquivo.

    Args:
        content: Conteúdo do arquivo.

    Returns:
        Hash em hexadecimal.
    """
    return hashlib.sha256(content).hexdigest()


def latest_source_file(conn: psycopg.Connection, source: str) -> SourceFile | None:
    """Lê a versão mais recente de um arquivo guardado na bronze.

    Args:
        conn: Conexão com o banco.
        source: Identificador do arquivo.

    Returns:
        O arquivo, ou ``None`` se nunca foi gravado.
    """
    row = conn.execute(
        """
        select run_id, content, content_hash
        from bronze.source_file
        where source = %s
        order by ingested_at desc, file_id desc
        limit 1
        """,
        (source,),
    ).fetchone()
    if row is None:
        return None
    return SourceFile(source, row[0], bytes(row[1]), row[2])


def insert_source_file(
    conn: psycopg.Connection, run_id: UUID, source: str, url: str, content: bytes
) -> None:
    """Grava uma versão de um arquivo em ``bronze.source_file`` (D-036).

    Args:
        conn: Conexão com o banco.
        run_id: Identificador da execução do pipeline.
        source: Identificador do arquivo.
        url: Endereço de onde o arquivo foi baixado.
        content: Bytes do arquivo, sem alteração.
    """
    conn.execute(
        """
        insert into bronze.source_file (
            run_id, source, url, content, content_hash, size_bytes
        ) values (%s, %s, %s, %s, %s, %s)
        """,
        (run_id, source, url, content, content_hash(content), len(content)),
    )


def read_observation_load(
    conn: psycopg.Connection, endpoint: str, period: str
) -> BronzeLoad | None:
    """Lê a carga mais recente de observações de um período (D-044).

    Args:
        conn: Conexão com o banco.
        endpoint: Caminho da requisição.
        period: Período no formato da API (ex.: ``"2000:2024"``).

    Returns:
        A carga, ou ``None`` se esse período nunca foi gravado.
    """
    rows = conn.execute(
        """
        select run_id, payload -> 1
        from bronze.api_response
        where endpoint = %(endpoint)s
          and params ->> 'date' = %(period)s
          and ingested_at = (
              select max(ingested_at) from bronze.api_response
              where endpoint = %(endpoint)s and params ->> 'date' = %(period)s
          )
        order by page
        """,
        {"endpoint": endpoint, "period": period},
    ).fetchall()
    if not rows:
        return None
    records = [record for _, page_records in rows for record in page_records or []]
    return BronzeLoad(endpoint, rows[0][0], records)


def country_codes(conn: psycopg.Connection) -> dict[str, str]:
    """Devolve o mapa de ``pais_iso2`` para ``pais_iso3`` (D-041).

    Args:
        conn: Conexão com o banco.

    Returns:
        O código ISO3 de cada código ISO2 em ``silver.dim_pais``.
    """
    rows = conn.execute("select pais_iso2, pais_iso3 from silver.dim_pais")
    return dict(rows.fetchall())


def start_pipeline_run(
    conn: psycopg.Connection, pipeline: str, params: dict[str, Any]
) -> UUID:
    """Registra o início de uma execução em ``etl.pipeline_run`` (D-046).

    Roda fora da transação da carga, para o registro sobreviver a uma falha.

    Args:
        conn: Conexão em modo autocommit.
        pipeline: Nome do comando.
        params: Parâmetros da execução.

    Returns:
        O identificador da execução.
    """
    run_id = uuid4()
    conn.execute(
        "insert into etl.pipeline_run (run_id, pipeline, params, status)"
        " values (%s, %s, %s, 'running')",
        (run_id, pipeline, Jsonb(params)),
    )
    return run_id


def finish_pipeline_run(
    conn: psycopg.Connection,
    run_id: UUID,
    status: str,
    bronze_run_ids: Sequence[UUID],
    rows_read: int | None = None,
    rows_written: int | None = None,
    error_message: str | None = None,
) -> None:
    """Registra o fim de uma execução em ``etl.pipeline_run`` (D-046).

    Args:
        conn: Conexão em modo autocommit.
        run_id: Identificador da execução.
        status: ``"success"``, ``"skipped"`` ou ``"failed"``.
        bronze_run_ids: Cargas da bronze lidas.
        rows_read: Linhas lidas da bronze.
        rows_written: Linhas inseridas ou alteradas.
        error_message: Mensagem de erro, em caso de falha.
    """
    conn.execute(
        """
        update etl.pipeline_run
        set status = %s, bronze_run_ids = %s::uuid[], rows_read = %s,
            rows_written = %s, error_message = %s, finished_at = now()
        where run_id = %s
        """,
        (status, list(bronze_run_ids), rows_read, rows_written, error_message, run_id),
    )


def last_successful_bronze_runs(
    conn: psycopg.Connection, pipeline: str, params: dict[str, Any]
) -> list[UUID] | None:
    """Busca as cargas lidas pela última execução bem-sucedida (D-045).

    Args:
        conn: Conexão com o banco.
        pipeline: Nome do comando.
        params: Parâmetros que a execução precisa ter usado.

    Returns:
        As cargas da bronze, ou ``None`` se não houve execução assim.
    """
    row = conn.execute(
        """
        select bronze_run_ids
        from etl.pipeline_run
        where pipeline = %s and params = %s and status = 'success'
        order by started_at desc
        limit 1
        """,
        (pipeline, Jsonb(params)),
    ).fetchone()
    return None if row is None else list(row[0])
