"""Pipeline dos arquivos fora da API: baixa e guarda o original na bronze."""

import logging
from typing import Literal
from uuid import uuid4

import psycopg

from world_bank.config import Settings
from world_bank.extract.source_files import download_xlsx
from world_bank.load.postgres import (
    content_hash,
    insert_source_file,
    latest_source_file,
)

logger = logging.getLogger(__name__)

INCOME_HISTORY_SOURCE = "income_history"


def run_source_files(
    conn: psycopg.Connection, settings: Settings
) -> Literal["inserted", "unchanged"]:
    """Grava o histórico de renda na bronze, se mudou desde a última carga (D-036).

    Args:
        conn: Conexão em modo autocommit.
        settings: Configurações (endereço do arquivo e timeout).

    Returns:
        ``"inserted"`` se gravou, ``"unchanged"`` se igual à última carga.

    Raises:
        SourceFileError: Se o download falhar. Nada é gravado.
    """
    url = settings.income_history_url
    content = download_xlsx(url, settings.request_timeout)
    latest = latest_source_file(conn, INCOME_HISTORY_SOURCE)
    changed = latest is None or latest.content_hash != content_hash(content)
    if changed:
        with conn.transaction():
            insert_source_file(conn, uuid4(), INCOME_HISTORY_SOURCE, url, content)
    status: Literal["inserted", "unchanged"] = "inserted" if changed else "unchanged"
    logger.info(
        "source file loaded",
        extra={
            "source": INCOME_HISTORY_SOURCE,
            "bytes": len(content),
            "status": status,
        },
    )
    return status
