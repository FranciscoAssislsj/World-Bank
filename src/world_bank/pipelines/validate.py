"""Comando ``validate``: inspeciona a silver sem alterar nenhum dado.

Roda todas as regras de ``sql/quality/`` e registra a execução e os resultados
(D-046, D-054). Erro faz o comando falhar; aviso só fica registrado (D-051).
"""

import logging

import psycopg

from world_bank.config import Settings
from world_bank.exceptions import LoadError, WorldBankError
from world_bank.load.postgres import (
    finish_pipeline_run,
    insert_quality_results,
    start_pipeline_run,
)
from world_bank.validate.checks import (
    CheckResult,
    check_params,
    load_checks,
    raise_for_errors,
    run_checks,
)

logger = logging.getLogger(__name__)

PIPELINE = "validate"


def run_validate(
    conn: psycopg.Connection, settings: Settings, start_year: int, end_year: int
) -> list[CheckResult]:
    """Roda todas as regras de qualidade.

    Args:
        conn: Conexão em modo autocommit.
        settings: Configurações (indicadores).
        start_year: Primeiro ano do período inspecionado.
        end_year: Último ano do período inspecionado.

    Returns:
        O resultado de cada regra.

    Raises:
        QualityCheckError: Se alguma regra de erro não passar.
        LoadError: Se o banco recusar a operação.
    """
    indicators = settings.indicators
    params = {"period": f"{start_year}:{end_year}", "indicators": indicators}
    run_id = start_pipeline_run(conn, PIPELINE, params)
    results: list[CheckResult] = []
    try:
        results = run_checks(
            conn, load_checks(), check_params(indicators, start_year, end_year)
        )
        raise_for_errors(results)
    except psycopg.Error as exc:
        error = LoadError(f"falha ao rodar as regras de qualidade: {exc}")
        finish_pipeline_run(conn, run_id, "failed", [], error_message=str(error))
        raise error from exc
    except WorldBankError as exc:
        insert_quality_results(conn, run_id, results)
        finish_pipeline_run(conn, run_id, "failed", [], error_message=str(exc))
        raise
    insert_quality_results(conn, run_id, results)
    finish_pipeline_run(conn, run_id, "success", [])
    logger.info(
        "validate finished",
        extra={
            "checks": len(results),
            "warnings": sum(not result.passed for result in results),
        },
    )
    return results
