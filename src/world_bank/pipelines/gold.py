"""Comando ``build-gold``: recria as views da gold a partir de ``sql/gold/``."""

import logging

import psycopg

from world_bank.load.gold import count_flagged_values, load_views, rebuild_views
from world_bank.pipelines.tracking import tracked_run

logger = logging.getLogger(__name__)

PIPELINE = "build-gold"


def run_gold(conn: psycopg.Connection) -> dict[str, int]:
    """Recria a gold e registra a execução (D-046, D-056).

    Args:
        conn: Conexão em modo autocommit.

    Returns:
        Quantas linhas cada view ficou com.

    Raises:
        ConfigurationError: Se um arquivo de ``sql/gold/`` for inválido. O banco não
            é alterado.
        LoadError: Se o banco recusar ou uma view ficar vazia. As views anteriores
            continuam.
    """
    with tracked_run(conn, PIPELINE, {}) as stats:
        counts = rebuild_views(conn, load_views())
        stats.rows_written = sum(counts.values())
        flagged = count_flagged_values(conn)
    if flagged:
        logger.warning(
            "values flagged as unusual",
            extra={"values": flagged, "see": "gold.valores_atipicos"},
        )
    logger.info("gold built", extra={"views": counts})
    return counts
