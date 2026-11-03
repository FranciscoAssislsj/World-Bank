"""Acesso ao PostgreSQL: conexão, migrações versionadas e gravação na bronze.

As migrações são arquivos ``sql/migrations/NNN_nome.sql`` aplicados em ordem.
Cada uma aplicada fica registrada em ``etl.schema_migrations`` com o checksum
do arquivo, para não rodar de novo e para detectar edição depois de aplicada.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from world_bank.config import Settings
from world_bank.exceptions import LoadError, MigrationError
from world_bank.extract.client import ApiPage

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "sql" / "migrations"

_MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")

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
