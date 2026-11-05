"""Como um número aparece na tela: só muda a escrita, nunca o valor (D-078)."""

SEM_DADO = "sem dado"
SINAL_MENOS = "−"  # o sinal de menos tipográfico
GRANDE = 1000


def numero(valor: float | None, casas: int = 1) -> str:
    """Escreve um número no padrão brasileiro.

    Args:
        valor: O número; ``None`` vira "sem dado", sem preencher (D-042).
        casas: Casas decimais.

    Returns:
        O texto, como ``"1.234,5"`` ou ``"−0,91"``.
    """
    if valor is None:
        return SEM_DADO
    texto = f"{abs(valor):,.{casas}f}".translate(str.maketrans(",.", ".,"))
    # Um valor que arredonda para zero fica "0,0", sem sinal.
    negativo = valor < 0 and any(c in "123456789" for c in texto)
    return f"{SINAL_MENOS}{texto}" if negativo else texto


def indicador(valor: float | None, casas_api: int | None) -> str:
    """Escreve o valor de um indicador agregado em um grupo de países.

    Parte das casas sugeridas pela API (D-047), com no mínimo uma casa, porque a
    média e a mediana de um grupo têm mais precisão que o dado de um país (D-081). Um
    número a partir de mil, como população ou PIB, fica sem casas.

    Args:
        valor: O valor agregado.
        casas_api: A coluna ``casas_decimais`` da gold.

    Returns:
        O texto do valor.
    """
    if valor is not None and abs(valor) >= GRANDE:
        return numero(valor, 0)
    return numero(valor, max(casas_api or 0, 1))
