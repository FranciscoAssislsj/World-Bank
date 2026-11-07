"""Camada gold: lê ``sql/gold/`` e recria as materialized views.

Cada arquivo tem o cabeçalho e uma única query, que roda como está em qualquer
cliente SQL. Este módulo cria a view, o índice e os comentários a partir dela (D-069).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import sql

from world_bank.exceptions import ConfigurationError, LoadError

GOLD_DIR = Path(__file__).resolve().parents[3] / "sql" / "gold"
SCHEMA = "gold"

_HEADER_LINE = re.compile(r"^-- (?P<key>[^:]+): (?P<value>.+)$")
# O número define a ordem: a estrela nasce antes das tabelas que a leem (D-088).
_FILE_NAME = re.compile(r"^\d{2}_(?P<name>[a-z0-9_]+)$")
_COLUMN_KEY = "Coluna "
_REQUIRED_KEYS = {
    "Pergunta de negócio",
    "Grão (o que é uma linha)",
    "Origem",
    "Regras",
    "Chave",
}
# Tira textos e comentários antes de procurar o ";" que separa dois comandos.
_LITERALS_AND_COMMENTS = re.compile(r"'(?:[^']|'')*'|--[^\n]*")


@dataclass(frozen=True)
class GoldView:
    """Uma view da gold lida do disco.

    Attributes:
        name: Nome do arquivo, sem ``.sql``, que é também o nome da view.
        description: Pergunta de negócio e grão, para o comentário da view.
        key: Colunas do grão, que formam o índice único (D-058).
        columns: Descrição de cada coluna, para os comentários (D-035).
        query: A consulta que calcula a tabela de análise.
    """

    name: str
    description: str
    key: tuple[str, ...]
    columns: dict[str, str]
    query: str


def parse_view(name: str, text: str) -> GoldView:
    """Interpreta o conteúdo de um arquivo da gold.

    Args:
        name: Nome do arquivo, sem ``.sql``.
        text: Conteúdo do arquivo.

    Returns:
        A view.

    Raises:
        ConfigurationError: Se o cabeçalho estiver incompleto, a primeira linha não
            nomear a view do arquivo, ou o corpo não for uma única consulta.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0].strip() != f"-- {SCHEMA}.{name}":
        raise ConfigurationError(
            f"gold {name}: a primeira linha precisa ser '-- {SCHEMA}.{name}'"
        )
    header: dict[str, str] = {}
    columns: dict[str, str] = {}
    body = lines[1:]
    while body and (match := _HEADER_LINE.match(body[0])):
        key, value = match["key"], match["value"].strip()
        if key.startswith(_COLUMN_KEY):
            columns[key.removeprefix(_COLUMN_KEY).strip()] = value
        else:
            header[key] = value
        body = body[1:]
    if missing := sorted(_REQUIRED_KEYS - header.keys()):
        raise ConfigurationError(f"gold {name}: cabeçalho sem {missing}")
    if not columns:
        raise ConfigurationError(f"gold {name}: cabeçalho sem descrição de colunas")
    query = "\n".join(body).strip().rstrip(";").strip()
    if not re.match(r"(select|with)\b", query, re.IGNORECASE):
        raise ConfigurationError(f"gold {name}: precisa começar por select ou with")
    if ";" in _LITERALS_AND_COMMENTS.sub("", query):
        raise ConfigurationError(f"gold {name}: o arquivo só pode ter uma query")
    return GoldView(
        name=name,
        description=(
            f"{header['Pergunta de negócio']} "
            f"Uma linha = {header['Grão (o que é uma linha)']}"
        ),
        key=tuple(column.strip() for column in header["Chave"].split(",")),
        columns=columns,
        query=query,
    )


def load_views(directory: Path = GOLD_DIR) -> list[GoldView]:
    """Lê as views do diretório, na ordem do número no início do nome (D-088).

    A estrela vem primeiro, porque as tabelas de consumo a leem (D-087).

    Args:
        directory: Diretório com os arquivos ``NN_nome.sql``.

    Returns:
        As views, na ordem de criação.

    Raises:
        ConfigurationError: Se um arquivo não tiver o número, repetir um nome, for
            inválido, ou se não houver nenhum.
    """
    views = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_NAME.match(path.stem)
        if match is None:
            raise ConfigurationError(f"gold {path.name}: use o nome NN_nome.sql")
        views.append(parse_view(match["name"], path.read_text(encoding="utf-8")))
    if not views:
        raise ConfigurationError(f"nenhuma view da gold em {directory}")
    names = [view.name for view in views]
    if repeated := sorted({name for name in names if names.count(name) > 1}):
        raise ConfigurationError(f"gold com nomes repetidos: {repeated}")
    return views


def _create_view(conn: psycopg.Connection, view: GoldView) -> int:
    identifier = sql.Identifier(SCHEMA, view.name)
    # A consulta vem de arquivos versionados do projeto, nunca de quem usa o programa.
    conn.execute(
        sql.SQL("create materialized view {view} as\n{query}").format(
            view=identifier, query=sql.SQL(view.query)
        )
    )
    # "nulls not distinct": renda e região são nulas em alguns recortes (D-058).
    conn.execute(
        sql.SQL("create unique index on {view} ({key}) nulls not distinct").format(
            view=identifier, key=sql.SQL(", ").join(map(sql.Identifier, view.key))
        )
    )
    conn.execute(
        sql.SQL("comment on materialized view {view} is {text}").format(
            view=identifier, text=sql.Literal(view.description)
        )
    )
    created = conn.execute(
        """
        select a.attname
        from pg_attribute a
        where a.attrelid = %s::regclass and a.attnum > 0 and not a.attisdropped
        """,
        (f"{SCHEMA}.{view.name}",),
    ).fetchall()
    created_names = {row[0] for row in created}
    if created_names != view.columns.keys():
        difference = sorted(created_names ^ view.columns.keys())
        raise LoadError(
            f"gold {view.name}: colunas sem descrição ou a mais: {difference}"
        )
    for column, text in view.columns.items():
        conn.execute(
            sql.SQL("comment on column {column} is {text}").format(
                column=sql.Identifier(SCHEMA, view.name, column),
                text=sql.Literal(text),
            )
        )
    row = conn.execute(
        sql.SQL("select count(*) from {view}").format(view=identifier)
    ).fetchone()
    return row[0]


def rebuild_views(conn: psycopg.Connection, views: list[GoldView]) -> dict[str, int]:
    """Recria a gold numa só transação, igual à pasta (D-056).

    Args:
        conn: Conexão em modo autocommit.
        views: Views lidas por ``load_views``.

    Returns:
        Quantas linhas cada view ficou com.

    Raises:
        LoadError: Se o banco recusar, se uma coluna não tiver descrição ou se uma
            view ficar vazia. A transação é desfeita, e as views anteriores continuam.
    """
    counts: dict[str, int] = {}
    try:
        with conn.transaction():
            existing = conn.execute(
                "select matviewname from pg_matviews where schemaname = %s", (SCHEMA,)
            ).fetchall()
            for (name,) in existing:
                conn.execute(
                    sql.SQL("drop materialized view if exists {view} cascade").format(
                        view=sql.Identifier(SCHEMA, name)
                    )
                )
            for view in views:
                counts[view.name] = _create_view(conn, view)
            if empty := sorted(name for name, rows in counts.items() if rows == 0):
                raise LoadError(f"views da gold vazias: {empty}")
    except psycopg.Error as exc:
        raise LoadError(f"falha ao recriar a gold: {exc}") from exc
    return counts


def count_flagged_values(conn: psycopg.Connection) -> int:
    """Conta os valores apontados como estranhos (D-062).

    Args:
        conn: Conexão com o banco.

    Returns:
        A quantidade de valores apontados.
    """
    row = conn.execute("select count(*) from gold.valores_atipicos").fetchone()
    return row[0]
