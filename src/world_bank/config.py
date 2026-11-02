"""Carregamento único e tipado das configurações do projeto.

Valores não sensíveis vêm de ``configs/{WB_ENV}.toml``. Variáveis de ambiente
(ou o arquivo ``.env``) têm prioridade sobre o TOML e são a única origem de
segredos, como ``DATABASE_URL``.
"""

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from world_bank.exceptions import ConfigurationError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

type Environment = Literal["dev", "prod"]

_SETTINGS_CONFIG = SettingsConfigDict(
    env_prefix="WB_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
)


class _EnvironmentSelector(BaseSettings):
    """Lê apenas ``WB_ENV`` (do ambiente ou do ``.env``)."""

    model_config = _SETTINGS_CONFIG

    env: Environment = "dev"


class Settings(BaseSettings):
    """Configurações do pipeline.

    Attributes:
        env: Ambiente ativo (``dev`` ou ``prod``).
        database_url: URL do PostgreSQL (segredo, vem de ``DATABASE_URL``).
        api_base_url: URL base da World Bank API v2.
        request_timeout: Timeout de cada requisição HTTP, em segundos.
        per_page: Registros por página pedidos à API.
        max_retries: Tentativas máximas para erros transitórios.
        source_id: Fonte (base) da API usada nas observações (2 = WDI).
        start_year: Primeiro ano extraído.
        end_year: Último ano extraído.
        indicators: Códigos dos indicadores extraídos.
        log_level: Nível mínimo de log.
    """

    model_config = _SETTINGS_CONFIG

    env: Environment = "dev"
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    api_base_url: str = "https://api.worldbank.org/v2"
    request_timeout: float = Field(default=30.0, gt=0)
    per_page: int = Field(default=1000, gt=0)
    max_retries: int = Field(default=5, ge=1)
    source_id: int = 2
    start_year: int = Field(default=2000, ge=1960)
    end_year: int = Field(default=2024, ge=1960)
    indicators: list[str] = Field(min_length=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _check_year_range(self) -> Self:
        if self.start_year > self.end_year:
            msg = f"start_year ({self.start_year}) > end_year ({self.end_year})"
            raise ValueError(msg)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Dá prioridade ao ambiente e ao ``.env`` sobre os valores do TOML."""
        return env_settings, dotenv_settings, init_settings


def load_settings(
    env: Environment | None = None, config_dir: Path = CONFIG_DIR
) -> Settings:
    """Carrega as configurações do ambiente escolhido.

    Args:
        env: Ambiente a usar. Se ``None``, usa ``WB_ENV`` (padrão ``dev``).
        config_dir: Diretório que contém os arquivos ``{env}.toml``.

    Returns:
        Configurações validadas.

    Raises:
        ConfigurationError: Se o arquivo do ambiente não existir ou se algum
            valor for inválido.
    """
    try:
        env_name = env or _EnvironmentSelector().env
    except ValidationError as exc:
        raise ConfigurationError(f"WB_ENV inválido: {exc}") from exc

    config_file = config_dir / f"{env_name}.toml"
    try:
        file_values = tomllib.loads(config_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        msg = f"arquivo de configuração ausente: {config_file}"
        raise ConfigurationError(msg) from exc

    try:
        return Settings(env=env_name, **file_values)
    except ValidationError as exc:
        msg = f"configuração inválida em {config_file}: {exc}"
        raise ConfigurationError(msg) from exc
