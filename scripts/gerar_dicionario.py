"""Gera docs/dicionario-dados.md a partir do catálogo do PostgreSQL.

O banco é a fonte: tipos, chaves e descrições (``comment on``) vêm dele, então o
arquivo não fica diferente do que existe (D-035). Rode depois de uma migração:

    uv run python scripts/gerar_dicionario.py
"""

from pathlib import Path

from world_bank.config import load_settings
from world_bank.load.postgres import connect

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "dicionario-dados.md"

SCHEMAS = {
    "gold": "Modelo estrela e indicadores prontos para os dashboards. Cada view vem "
    "de um arquivo em `sql/gold/`.",
    "silver": "Tratamento: dado limpo, tipado e ligado por chaves.",
    "bronze": "Dado como veio da fonte, sem alteração. Serve para auditar.",
    "etl": "Controle do pipeline.",
}

VALUE_TYPES = {
    "text": "texto",
    "integer": "número inteiro",
    "smallint": "número inteiro",
    "bigint": "número inteiro",
    "numeric": "número decimal",
    "boolean": "verdadeiro/falso",
    "date": "data",
    "timestamp with time zone": "data e hora",
    "uuid": "identificador único",
    "uuid[]": "lista de identificadores",
    "jsonb": "JSON",
    "bytea": "arquivo (bytes)",
}

HEADER = """# Dicionário de dados

Colunas de cada tabela, com o tipo de valor e o que significam. Veja também o
[diagrama das ligações](modelagem-gold.svg) e os motivos das decisões em
[data-decisions.md](data-decisions.md).

> Gerado por `scripts/gerar_dicionario.py` a partir do banco. Não edite à mão: para
> mudar uma descrição, altere o `comment on` numa migração, ou o cabeçalho do arquivo
> em `sql/gold/`, e gere de novo.

**Como ler:** *PK* identifica a linha. *FK* aponta para outra tabela. *único* não se
repete. *Vazio?* diz se a coluna aceita ficar sem valor (`NULL`).
"""

TABLES_SQL = """
    select c.oid, c.relname, obj_description(c.oid)
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = %s and c.relkind in ('r', 'v', 'm')
    order by c.relname
"""

COLUMNS_SQL = """
    select a.attname, format_type(a.atttypid, null), not a.attnotnull,
           coalesce(col_description(a.attrelid, a.attnum), '')
    from pg_attribute a
    where a.attrelid = %s and a.attnum > 0 and not a.attisdropped
    order by a.attnum
"""

KEYS_SQL = """
    select a.attname, k.contype, f.relname, fa.attname
    from pg_constraint k
    cross join lateral unnest(k.conkey) with ordinality as own (attnum, position)
    join pg_attribute a on a.attrelid = k.conrelid and a.attnum = own.attnum
    left join pg_class f on f.oid = k.confrelid
    left join pg_attribute fa
        on fa.attrelid = k.confrelid and fa.attnum = k.confkey[own.position]
    where k.conrelid = %s and k.contype in ('p', 'u', 'f')
    order by k.contype desc
"""


def key_labels(conn, table_oid) -> dict[str, list[str]]:
    """Devolve as marcas de chave (PK, FK, único) de cada coluna da tabela."""
    labels: dict[str, list[str]] = {}
    for column, kind, target, target_column in conn.execute(KEYS_SQL, (table_oid,)):
        label = {"p": "PK", "u": "único"}.get(kind, f"FK → `{target}.{target_column}`")
        labels.setdefault(column, []).append(label)
    return labels


def render_table(conn, schema: str, oid, name: str, description: str | None) -> str:
    """Monta a seção de uma tabela."""
    keys = key_labels(conn, oid)
    lines = [
        f"### `{schema}.{name}`",
        "",
        description or "",
        "",
        "| Coluna | Tipo de valor | Tipo no banco | Vazio? | Chave | Descrição |",
        "|---|---|---|---|---|---|",
    ]
    for column, db_type, nullable, text in conn.execute(COLUMNS_SQL, (oid,)):
        lines.append(
            f"| `{column}` | {VALUE_TYPES[db_type]} | `{db_type}` "
            f"| {'sim' if nullable else 'não'} | {', '.join(keys.get(column, []))} "
            f"| {text} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Lê o catálogo e grava o arquivo."""
    sections = [HEADER]
    with connect(load_settings()) as conn:
        for schema, intro in SCHEMAS.items():
            sections.append(f"## Camada `{schema}`\n\n{intro}\n")
            tables = conn.execute(TABLES_SQL, (schema,)).fetchall()
            sections.extend(
                render_table(conn, schema, oid, name, description)
                for oid, name, description in tables
            )
    OUTPUT.write_text("\n".join(sections), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
