"""Ponto de entrada da CLI: ``uv run python -m world_bank <comando>``."""

import argparse
import logging

from world_bank.config import load_settings
from world_bank.logging_config import configure_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser da linha de comando.

    Returns:
        Parser com os subcomandos disponíveis.
    """
    parser = argparse.ArgumentParser(
        prog="world_bank",
        description="Pipeline World Bank API v2 -> PostgreSQL (bronze, silver, gold).",
    )
    parser.add_subparsers(dest="command", metavar="<comando>")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI.

    Args:
        argv: Argumentos da linha de comando (``None`` usa ``sys.argv``).

    Returns:
        Código de saída do processo (0 = sucesso).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_level)
    logger.info("settings loaded", extra={"env": settings.env})

    if args.command is None:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
