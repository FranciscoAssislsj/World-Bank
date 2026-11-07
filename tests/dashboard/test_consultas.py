"""Toda consulta do dashboard lê só a gold, e nenhuma cola filtro no texto."""

import re
from decimal import Decimal

import psycopg
import pytest
from pytest_mock import MockerFixture

from world_bank.dashboard import consultas
from world_bank.exceptions import LoadError

CONSULTAS = {
    nome: valor
    for nome, valor in vars(consultas).items()
    if nome.isupper() and not nome.startswith("_") and isinstance(valor, str)
}
_ORIGEM = re.compile(r"\b(?:from|join)\s+([^\s(]+)", re.IGNORECASE)


def test_existem_consultas() -> None:
    assert len(CONSULTAS) >= 8


@pytest.mark.parametrize("nome", sorted(CONSULTAS))
def test_consulta_le_so_a_gold(nome: str) -> None:
    origens = _ORIGEM.findall(CONSULTAS[nome])

    assert origens, nome
    assert all(origem.startswith("gold.") for origem in origens), origens


@pytest.mark.parametrize("nome", sorted(CONSULTAS))
def test_consulta_nao_escreve(nome: str) -> None:
    proibido = r"\b(insert|update|delete|drop|alter|create|truncate|grant)\b"

    assert not re.search(proibido, CONSULTAS[nome], re.IGNORECASE)


@pytest.mark.parametrize("nome", sorted(CONSULTAS))
def test_consulta_nao_calcula(nome: str) -> None:
    """A consulta só escolhe colunas e linhas; toda conta fica na gold (D-097)."""
    sql = re.sub(r"'[^']*'", "''", CONSULTAS[nome])  # sem os textos entre aspas
    sql = re.sub(r"%\(\w+\)s(::\w+)?", "?", sql)  # sem os parâmetros

    assert not re.search(r"[-+*/]", sql), "operação aritmética"
    funcoes = r"\b(sum|avg|count|min|max|rank|row_number|coalesce|round|case|limit)\b"
    assert not re.search(funcoes, sql, re.IGNORECASE)
    assert not re.search(r"=\s*''\s+as\b", sql), "comparação virando coluna"


def test_ler_troca_decimal_por_float(mocker: MockerFixture) -> None:
    connect = mocker.patch("world_bank.dashboard.consultas.psycopg.connect")
    conn = connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchall.return_value = [
        {"pais": "Brazil", "valor": Decimal("1.5"), "ano": 2023}
    ]

    linhas = consultas.ler("url", "select 1", {"ano": 2023})

    assert linhas == [{"pais": "Brazil", "valor": 1.5, "ano": 2023}]
    assert isinstance(linhas[0]["valor"], float)
    conn.execute.assert_called_once_with("select 1", {"ano": 2023})
    assert connect.call_args.kwargs["connect_timeout"] > 0


def test_ler_transforma_erro_do_banco(mocker: MockerFixture) -> None:
    mocker.patch(
        "world_bank.dashboard.consultas.psycopg.connect",
        side_effect=psycopg.OperationalError("banco desligado"),
    )

    with pytest.raises(LoadError, match="não foi possível ler a gold"):
        consultas.ler("url", "select 1")
