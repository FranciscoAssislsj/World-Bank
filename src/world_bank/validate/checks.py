"""Regras de qualidade: lê ``sql/quality/``, roda cada regra e monta o resultado.

Cada arquivo é uma consulta que devolve as linhas com problema (D-049). Nenhuma
linha significa que a regra passou. Erro bloqueia; aviso só registra (D-051).
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from world_bank.exceptions import ConfigurationError, QualityCheckError
from world_bank.extract.endpoints import chunk_indicators

logger = logging.getLogger(__name__)

QUALITY_DIR = Path(__file__).resolve().parents[3] / "sql" / "quality"

_HEADER_LINE = re.compile(r"^-- (?P<key>[a-z]+): (?P<value>.+)$")
_HEADER_KEYS = {"pergunta", "severidade", "grupo", "origem", "decisao"}
_SEVERITIES = {"erro": "error", "aviso": "warning"}
_GROUPS = {"fato", "geral"}
_SAMPLE_SIZE = 5


@dataclass(frozen=True)
class QualityCheck:
    """Uma regra de qualidade lida do disco.

    Attributes:
        name: Nome do arquivo, sem ``.sql``.
        question: O que a regra verifica.
        severity: ``"error"`` ou ``"warning"``.
        group: ``"fato"`` roda também em ``load-observations``; ``"geral"`` só no
            ``validate``.
        decision: Decisão que justifica a regra.
        query: Consulta que devolve as linhas com problema.
    """

    name: str
    question: str
    severity: str
    group: str
    decision: str
    query: str


@dataclass(frozen=True)
class CheckResult:
    """O resultado de uma regra.

    Attributes:
        name: Nome da regra.
        severity: ``"error"`` ou ``"warning"``.
        passed: ``True`` quando não há linhas com problema.
        rows_failed: Linhas com problema.
        sample: Até 5 exemplos.
    """

    name: str
    severity: str
    passed: bool
    rows_failed: int
    sample: list[Any]


def parse_check(name: str, text: str) -> QualityCheck:
    """Interpreta o conteúdo de um arquivo de regra.

    Args:
        name: Nome da regra.
        text: Conteúdo do arquivo.

    Returns:
        A regra.

    Raises:
        ConfigurationError: Se o cabeçalho estiver incompleto ou inválido.
    """
    header: dict[str, str] = {}
    body: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        match = _HEADER_LINE.match(line)
        if match and not body:
            header[match["key"]] = match["value"].strip()
        else:
            body.append(line)
    if missing := sorted(_HEADER_KEYS - header.keys()):
        raise ConfigurationError(f"regra {name}: cabeçalho sem {missing}")
    if header["severidade"] not in _SEVERITIES:
        raise ConfigurationError(f"regra {name}: severidade inválida")
    if header["grupo"] not in _GROUPS:
        raise ConfigurationError(f"regra {name}: grupo inválido")
    query = "\n".join(body).strip().rstrip(";").strip()
    if not query:
        raise ConfigurationError(f"regra {name}: arquivo sem consulta")
    return QualityCheck(
        name=name,
        question=header["pergunta"],
        severity=_SEVERITIES[header["severidade"]],
        group=header["grupo"],
        decision=header["decisao"],
        query=query,
    )


def load_checks(
    group: str | None = None, directory: Path = QUALITY_DIR
) -> list[QualityCheck]:
    """Lê as regras do diretório, em ordem de nome.

    Args:
        group: Se informado, devolve só as regras desse grupo.
        directory: Diretório com os arquivos ``.sql``.

    Returns:
        As regras.

    Raises:
        ConfigurationError: Se algum arquivo for inválido ou não houver regras.
    """
    checks = [
        parse_check(path.stem, path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.sql"))
    ]
    if not checks:
        raise ConfigurationError(f"nenhuma regra de qualidade em {directory}")
    return [check for check in checks if group is None or check.group == group]


def check_params(
    indicators: list[str], start_year: int, end_year: int
) -> dict[str, Any]:
    """Monta os parâmetros que as consultas das regras recebem.

    Args:
        indicators: Indicadores configurados.
        start_year: Primeiro ano.
        end_year: Último ano.

    Returns:
        Parâmetros nomeados para as consultas.
    """
    return {
        "indicators": indicators,
        "start_year": start_year,
        "end_year": end_year,
        "period": f"{start_year}:{end_year}",
        "endpoints": [
            f"country/all/indicator/{';'.join(chunk)}"
            for chunk in chunk_indicators(indicators)
        ],
    }


def run_check(
    conn: psycopg.Connection, check: QualityCheck, params: dict[str, Any]
) -> CheckResult:
    """Roda uma regra: conta as linhas com problema e guarda alguns exemplos.

    Args:
        conn: Conexão com o banco.
        check: Regra a rodar.
        params: Parâmetros da consulta.

    Returns:
        O resultado.
    """
    # A consulta vem de arquivos versionados do projeto, nunca de quem usa o programa.
    query = sql.SQL(
        "select to_jsonb(problema), count(*) over ()\n"
        "from (\n{query}\n) as problema\nlimit {limit}"
    ).format(query=sql.SQL(check.query), limit=sql.Literal(_SAMPLE_SIZE))
    rows = conn.execute(query, params).fetchall()
    total = rows[0][1] if rows else 0
    return CheckResult(
        name=check.name,
        severity=check.severity,
        passed=total == 0,
        rows_failed=total,
        sample=[row[0] for row in rows],
    )


def run_checks(
    conn: psycopg.Connection, checks: Sequence[QualityCheck], params: dict[str, Any]
) -> list[CheckResult]:
    """Roda as regras e registra no log cada uma que não passou.

    Args:
        conn: Conexão com o banco.
        checks: Regras a rodar.
        params: Parâmetros das consultas.

    Returns:
        Um resultado por regra.
    """
    results = [run_check(conn, check, params) for check in checks]
    for result in results:
        if not result.passed:
            log = logger.error if result.severity == "error" else logger.warning
            log(
                "quality check failed",
                extra={"check": result.name, "rows_failed": result.rows_failed},
            )
    return results


def raise_for_errors(results: Sequence[CheckResult]) -> None:
    """Levanta um erro se alguma regra de severidade ``error`` não passou.

    Args:
        results: Resultados das regras.

    Raises:
        QualityCheckError: Com o nome e a quantidade de cada regra reprovada.
    """
    failed = [r for r in results if r.severity == "error" and not r.passed]
    if failed:
        details = ", ".join(f"{r.name} ({r.rows_failed})" for r in failed)
        raise QualityCheckError(f"regras de qualidade reprovadas: {details}")
