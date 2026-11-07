"""Confere que a documentação acompanha o projeto, sem rede e sem banco (D-091)."""

import argparse
import re
from pathlib import Path

import pytest

from world_bank.__main__ import build_parser

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _gold_files() -> list[str]:
    return sorted(path.name for path in (ROOT / "sql" / "gold").glob("*.sql"))


def _commands() -> list[str]:
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return sorted(action.choices)
    raise AssertionError("a CLI não tem subcomandos")


def _env_variables() -> list[str]:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return re.findall(r"^#? ?([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE)


def _relative_links(markdown: str) -> list[str]:
    return [
        target.split("#")[0]
        for target in LINK.findall(markdown)
        if not target.startswith(("http://", "https://", "#"))
    ]


def test_finds_what_it_checks() -> None:
    assert _gold_files()
    assert "run-all" in _commands()
    assert "COMPOSE_PROFILES" in _env_variables()
    assert "docs/data-decisions.md" in _relative_links(README)


@pytest.mark.parametrize("file_name", _gold_files())
def test_readme_links_each_gold_file(file_name: str) -> None:
    assert f"(sql/gold/{file_name})" in README


@pytest.mark.parametrize("command", _commands())
def test_pipelines_page_describes_each_command(command: str) -> None:
    page = (ROOT / "docs" / "pipelines.md").read_text(encoding="utf-8")

    assert f"`{command}`" in page


@pytest.mark.parametrize("variable", _env_variables())
def test_configuration_page_describes_each_variable(variable: str) -> None:
    page = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")

    assert f"`{variable}`" in page


@pytest.mark.parametrize("target", sorted(set(_relative_links(README))))
def test_readme_relative_link_exists(target: str) -> None:
    assert (ROOT / target).exists()
