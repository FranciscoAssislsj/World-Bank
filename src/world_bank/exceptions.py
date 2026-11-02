"""Exceções do domínio do pipeline World Bank."""


class WorldBankError(Exception):
    """Base de todas as exceções do projeto."""


class ConfigurationError(WorldBankError):
    """Configuração ausente ou inválida."""


class ApiResponseError(WorldBankError):
    """Resposta da API com erro, inclusive erros devolvidos com HTTP 200.

    Attributes:
        code: Código de erro da API (ex.: "120"), quando disponível.
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code

    def __str__(self) -> str:
        base = super().__str__()
        return f"{base} (code={self.code})" if self.code else base


class TransientApiError(ApiResponseError):
    """Erro temporário da API (HTTP 5xx, falha de rede ou códigos 105/199).

    É o único tipo de erro que o cliente tenta de novo.
    """


class SchemaValidationError(WorldBankError):
    """Dados que não respeitam o esquema ou as regras de qualidade esperadas."""


class LoadError(WorldBankError):
    """Falha ao persistir dados no banco."""
