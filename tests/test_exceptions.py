import pytest

from world_bank.exceptions import (
    ApiResponseError,
    ConfigurationError,
    LoadError,
    SchemaValidationError,
    WorldBankError,
)


@pytest.mark.parametrize(
    "exc_class",
    [ApiResponseError, ConfigurationError, LoadError, SchemaValidationError],
)
def test_domain_exceptions_share_base_class(exc_class: type[Exception]) -> None:
    assert issubclass(exc_class, WorldBankError)


def test_api_response_error_keeps_code() -> None:
    error = ApiResponseError("Invalid value", code="120")

    assert error.code == "120"
    assert str(error) == "Invalid value (code=120)"


def test_api_response_error_without_code() -> None:
    error = ApiResponseError("timeout")

    assert error.code is None
    assert str(error) == "timeout"
