import pytest

from world_bank.dashboard.formato import indicador, numero


@pytest.mark.parametrize(
    ("valor", "casas", "esperado"),
    [
        (None, 1, "sem dado"),
        (74.6, 1, "74,6"),
        (106374.6, 1, "106.374,6"),
        (-0.91, 2, "−0,91"),
        (-0.04, 1, "0,0"),
        (0, 1, "0,0"),
        (1438069596, 0, "1.438.069.596"),
    ],
)
def test_numero(valor: float | None, casas: int, esperado: str) -> None:
    assert numero(valor, casas) == esperado


@pytest.mark.parametrize(
    ("valor", "casas_api", "esperado"),
    [
        (74.6, 0, "74,6"),
        (3.14159, 2, "3,14"),
        (None, 1, "sem dado"),
        (2500.7, 1, "2.501"),
        (9.9, None, "9,9"),
    ],
)
def test_indicador(valor: float | None, casas_api: int | None, esperado: str) -> None:
    assert indicador(valor, casas_api) == esperado
