import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from world_bank.exceptions import ConfigurationError, QualityCheckError
from world_bank.validate.checks import (
    CheckResult,
    QualityCheck,
    check_params,
    load_checks,
    parse_check,
    raise_for_errors,
    run_check,
    run_checks,
)

VALID = """-- pergunta: Algum valor passa de 50%?
-- severidade: erro
-- grupo: fato
-- origem: silver.tabela
-- decisao: D-001
select a
from silver.tabela
where a > %(limite)s;
"""


def _check(severity: str = "error") -> QualityCheck:
    return QualityCheck("regra", "Pergunta?", severity, "fato", "D-001", "select 1")


def _result(severity: str, passed: bool, rows: int = 0) -> CheckResult:
    return CheckResult("regra", severity, passed, rows, [])


def _fake_conn(rows: list[tuple[object, int]]) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = rows
    return conn


def test_parse_check_reads_header_and_query() -> None:
    check = parse_check("regra", VALID)

    assert check.name == "regra"
    assert check.question == "Algum valor passa de 50%?"
    assert (check.severity, check.group, check.decision) == ("error", "fato", "D-001")
    assert check.query == "select a\nfrom silver.tabela\nwhere a > %(limite)s"


def test_parse_check_accepts_windows_line_endings() -> None:
    assert parse_check("regra", VALID.replace("\n", "\r\n")).severity == "error"


def test_warning_severity_is_translated() -> None:
    text = VALID.replace("severidade: erro", "severidade: aviso")

    assert parse_check("regra", text).severity == "warning"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("-- decisao: D-001\n", "", "cabeçalho sem"),
        ("severidade: erro", "severidade: grave", "severidade inválida"),
        ("grupo: fato", "grupo: outro", "grupo inválido"),
    ],
)
def test_invalid_header_fails(old: str, new: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        parse_check("regra", VALID.replace(old, new))


def test_file_without_query_fails() -> None:
    text = VALID[: VALID.index("select")]

    with pytest.raises(ConfigurationError, match="sem consulta"):
        parse_check("regra", text)


def test_load_checks_filters_by_group_in_name_order(tmp_path: Path) -> None:
    (tmp_path / "b.sql").write_text(VALID, encoding="utf-8")
    (tmp_path / "a.sql").write_text(VALID, encoding="utf-8")
    (tmp_path / "c.sql").write_text(
        VALID.replace("grupo: fato", "grupo: geral"), encoding="utf-8"
    )

    assert [c.name for c in load_checks(directory=tmp_path)] == ["a", "b", "c"]
    assert [c.name for c in load_checks("fato", tmp_path)] == ["a", "b"]


def test_load_checks_fails_on_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="nenhuma regra"):
        load_checks(directory=tmp_path)


def test_project_rules_are_complete() -> None:
    checks = load_checks()

    assert len(checks) == 16
    assert sum(c.severity == "error" for c in checks) == 8
    assert sum(c.group == "fato" for c in checks) == 7
    assert all(re.fullmatch(r"D-\d{3}", c.decision) for c in checks)
    assert all(c.question.endswith("?") for c in checks)


def test_check_params_builds_period_and_endpoint() -> None:
    assert check_params(["AA", "BB"], 2000, 2024) == {
        "indicators": ["AA", "BB"],
        "start_year": 2000,
        "end_year": 2024,
        "period": "2000:2024",
        "endpoints": ["country/all/indicator/AA;BB"],
    }


def test_run_check_without_rows_passes() -> None:
    result = run_check(_fake_conn([]), _check(), {})

    assert result == CheckResult("regra", "error", True, 0, [])


def test_run_check_with_rows_fails_and_keeps_sample() -> None:
    conn = _fake_conn([({"a": 1}, 7), ({"a": 2}, 7)])

    result = run_check(conn, _check(), {"x": 1})

    assert result == CheckResult("regra", "error", False, 7, [{"a": 1}, {"a": 2}])
    query, params = conn.execute.call_args.args
    assert "limit 5" in query.as_string()
    assert "select 1" in query.as_string()
    assert params == {"x": 1}


def test_run_checks_logs_only_failed_rules(caplog: pytest.LogCaptureFixture) -> None:
    conn = _fake_conn([({"a": 1}, 2)])

    with caplog.at_level("WARNING"):
        results = run_checks(conn, [_check("warning"), _check("error")], {})

    assert len(results) == 2
    assert [r.levelname for r in caplog.records] == ["WARNING", "ERROR"]


def test_passed_rules_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        run_checks(_fake_conn([]), [_check()], {})

    assert caplog.records == []


def test_raise_for_errors_names_failed_rules() -> None:
    results = [_result("error", False, 3), _result("warning", False, 9)]

    with pytest.raises(QualityCheckError, match=r"regra \(3\)"):
        raise_for_errors(results)


@pytest.mark.parametrize(
    "results",
    [[], [_result("error", True)], [_result("warning", False, 9)]],
)
def test_raise_for_errors_accepts_passed_rules_and_warnings(
    results: list[CheckResult],
) -> None:
    raise_for_errors(results)
