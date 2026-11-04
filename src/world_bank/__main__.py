"""Ponto de entrada da CLI: ``uv run python -m world_bank <comando>``."""

import argparse
import logging

from world_bank.config import Settings, load_settings
from world_bank.exceptions import WorldBankError
from world_bank.extract.client import WorldBankClient
from world_bank.load.postgres import apply_migrations, connect, list_migrations
from world_bank.logging_config import configure_logging
from world_bank.pipelines.bronze import run_bronze
from world_bank.pipelines.dimensions import run_dimensions
from world_bank.pipelines.source_files import run_source_files

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
    commands = parser.add_subparsers(dest="command", metavar="<comando>")
    commands.add_parser(
        "migrate", help="aplica as migrações pendentes de sql/migrations/"
    )
    load_bronze = commands.add_parser(
        "load-bronze", help="grava na bronze as respostas da API e o histórico de renda"
    )
    load_bronze.add_argument(
        "--start", type=int, help="primeiro ano das observações (padrão: config)"
    )
    load_bronze.add_argument(
        "--end", type=int, help="último ano das observações (padrão: config)"
    )
    commands.add_parser(
        "load-dimensions", help="grava as dimensões da silver a partir da bronze"
    )
    return parser


def run_migrate(settings: Settings) -> None:
    """Aplica as migrações pendentes e registra quantas rodaram.

    Args:
        settings: Configurações com ``DATABASE_URL``.
    """
    migrations = list_migrations()
    with connect(settings) as conn:
        applied = apply_migrations(conn, migrations)
    logger.info(
        "migrate finished",
        extra={
            "applied": len(applied),
            "already_applied": len(migrations) - len(applied),
        },
    )


def run_load_bronze(
    settings: Settings, start_year: int | None, end_year: int | None
) -> None:
    """Busca os dados na API e grava as requisições que mudaram na bronze.

    Args:
        settings: Configurações (API, banco, indicadores e período).
        start_year: Primeiro ano; ``None`` usa ``settings.start_year``.
        end_year: Último ano; ``None`` usa ``settings.end_year``.
    """
    with WorldBankClient.from_settings(settings) as client, connect(settings) as conn:
        run_bronze(
            client,
            conn,
            settings,
            start_year or settings.start_year,
            end_year or settings.end_year,
        )
        run_source_files(conn, settings)


def run_load_dimensions(settings: Settings) -> None:
    """Lê os cadastros da bronze e grava as dimensões da silver.

    Args:
        settings: Configurações (banco e indicadores).
    """
    with connect(settings) as conn:
        run_dimensions(conn, settings)


def main(argv: list[str] | None = None) -> int:
    """Executa a CLI.

    Args:
        argv: Argumentos da linha de comando (``None`` usa ``sys.argv``).

    Returns:
        Código de saída do processo (0 = sucesso, 1 = erro do pipeline).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_level)
    logger.info("settings loaded", extra={"env": settings.env})

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "migrate":
            run_migrate(settings)
        elif args.command == "load-bronze":
            run_load_bronze(settings, args.start, args.end)
        elif args.command == "load-dimensions":
            run_load_dimensions(settings)
    except WorldBankError:
        logger.exception("command failed", extra={"command": args.command})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
