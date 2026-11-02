"""Cliente HTTP da World Bank API v2: paginação, retry e detecção de erro no corpo."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Self

import httpx
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from world_bank.config import Settings
from world_bank.exceptions import ApiResponseError, TransientApiError

logger = logging.getLogger(__name__)

TRANSIENT_ERROR_CODES = frozenset({"105", "199"})
MAX_BACKOFF_SECONDS = 30.0


@dataclass(frozen=True)
class ApiPage:
    """Uma página de resposta da API, com o JSON original preservado.

    Attributes:
        path: Caminho do endpoint (ex.: ``"country"``).
        params: Parâmetros enviados, inclusive ``page``, ``per_page`` e ``format``.
        page: Número desta página.
        pages: Total de páginas informado pela API.
        total: Total de registros informado pela API.
        payload: Resposta JSON exatamente como veio (``[metadados, registros]``).
        metadata: Primeiro elemento do payload.
        records: Registros da página (lista vazia quando a API devolve ``None``).
    """

    path: str
    params: dict[str, str]
    page: int
    pages: int
    total: int
    payload: list[Any]
    metadata: dict[str, Any]
    records: list[dict[str, Any]]


def parse_payload(payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Separa metadados e registros de uma resposta JSON da API v2.

    Args:
        payload: JSON decodificado da resposta.

    Returns:
        Tupla ``(metadados, registros)``. Registros ``None`` viram lista vazia.

    Raises:
        TransientApiError: Se o corpo trouxer um erro temporário (105 ou 199).
        ApiResponseError: Se o corpo trouxer outro erro ou tiver estrutura
            inesperada.
    """
    if (
        isinstance(payload, list)
        and payload
        and isinstance(payload[0], dict)
        and "message" in payload[0]
    ):
        raise _error_from_messages(payload[0]["message"])

    if not (
        isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], dict)
    ):
        raise ApiResponseError(
            f"estrutura inesperada da resposta: {str(payload)[:200]}"
        )

    metadata, records = payload
    if records is None:
        return metadata, []
    if not isinstance(records, list):
        raise ApiResponseError(f"registros não são uma lista: {type(records).__name__}")
    return metadata, records


def _error_from_messages(messages: Any) -> ApiResponseError:
    first = messages[0] if isinstance(messages, list) and messages else {}
    if not isinstance(first, dict):
        first = {}
    code = str(first.get("id", "")) or None
    text = first.get("value") or first.get("key") or "erro sem descrição"
    error_class = (
        TransientApiError if code in TRANSIENT_ERROR_CODES else ApiResponseError
    )
    return error_class(f"API devolveu erro: {text}", code=code)


class WorldBankClient:
    """Cliente da World Bank API v2.

    Sempre envia ``format=json`` e ``per_page``, percorre todas as páginas e
    tenta de novo só os erros temporários, com backoff exponencial.

    Exemplo:
        >>> with WorldBankClient.from_settings(settings) as client:
        ...     regions = client.get_all("region")
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        per_page: int = 1000,
        max_retries: int = 5,
        backoff_seconds: float = 1.0,
    ) -> None:
        """Cria o cliente.

        Args:
            base_url: URL base da API (ex.: ``https://api.worldbank.org/v2``).
            timeout: Timeout de cada requisição, em segundos.
            per_page: Registros pedidos por página.
            max_retries: Tentativas máximas por página (inclui a primeira).
            backoff_seconds: Espera base do backoff (1, 2, 4... vezes este valor).
        """
        self._http = httpx.Client(base_url=base_url, timeout=timeout)
        self._per_page = per_page
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        """Cria o cliente a partir das configurações do projeto.

        Args:
            settings: Configurações carregadas por ``load_settings``.

        Returns:
            Cliente configurado.
        """
        return cls(
            settings.api_base_url,
            timeout=settings.request_timeout,
            per_page=settings.per_page,
            max_retries=settings.max_retries,
        )

    def close(self) -> None:
        """Fecha as conexões HTTP abertas."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def iter_pages(
        self, path: str, params: dict[str, str] | None = None
    ) -> Iterator[ApiPage]:
        """Percorre todas as páginas de um endpoint, da 1 até ``pages``.

        Args:
            path: Caminho do endpoint, relativo à URL base (ex.: ``"country"``).
            params: Parâmetros extras (ex.: ``{"date": "2000:2024"}``).

        Yields:
            Cada página, na ordem.

        Raises:
            ApiResponseError: Se alguma página falhar de forma definitiva.
        """
        page_number, pages = 1, 1
        while page_number <= pages:
            api_page = self.get_page(path, params or {}, page_number)
            pages = api_page.pages
            yield api_page
            page_number += 1

    def get_all(
        self, path: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Busca e concatena os registros de todas as páginas de um endpoint.

        Args:
            path: Caminho do endpoint, relativo à URL base.
            params: Parâmetros extras.

        Returns:
            Todos os registros, na ordem das páginas.

        Raises:
            ApiResponseError: Se alguma página falhar de forma definitiva.
        """
        return [
            record for page in self.iter_pages(path, params) for record in page.records
        ]

    def get_page(self, path: str, params: dict[str, str], page: int) -> ApiPage:
        """Busca uma única página, com retry para erros temporários.

        Args:
            path: Caminho do endpoint, relativo à URL base.
            params: Parâmetros extras; ``format``, ``per_page`` e ``page`` são
                sempre definidos pelo cliente.
            page: Número da página.

        Returns:
            A página com o payload original e os metadados lidos.

        Raises:
            TransientApiError: Se o erro temporário persistir após todas as
                tentativas.
            ApiResponseError: Se a API devolver um erro definitivo.
        """
        request_params = {
            **params,
            "format": "json",
            "per_page": str(self._per_page),
            "page": str(page),
        }
        payload, metadata, records = self._fetch_with_retry(path, request_params)
        api_page = ApiPage(
            path=path,
            params=request_params,
            page=int(metadata.get("page") or page),
            pages=int(metadata.get("pages") or 0),
            total=int(metadata.get("total") or 0),
            payload=payload,
            metadata=metadata,
            records=records,
        )
        logger.debug(
            "page fetched",
            extra={
                "endpoint": path,
                "page": api_page.page,
                "pages": api_page.pages,
                "records": len(records),
            },
        )
        return api_page

    def _fetch_with_retry(
        self, path: str, params: dict[str, str]
    ) -> tuple[list[Any], dict[str, Any], list[dict[str, Any]]]:
        retrying = Retrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(
                multiplier=self._backoff_seconds, max=MAX_BACKOFF_SECONDS
            ),
            retry=retry_if_exception_type((TransientApiError, httpx.TransportError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        try:
            return retrying(self._fetch, path, params)
        except httpx.TransportError as exc:
            msg = (
                f"falha de rede em {path} após {self._max_retries} tentativas: "
                f"{type(exc).__name__}"
            )
            raise TransientApiError(msg) from exc

    def _fetch(
        self, path: str, params: dict[str, str]
    ) -> tuple[list[Any], dict[str, Any], list[dict[str, Any]]]:
        response = self._http.get(path, params=params)
        status = response.status_code
        if status >= 500:
            raise TransientApiError(f"HTTP {status} em {path}", code=str(status))
        if response.is_error:
            raise ApiResponseError(f"HTTP {status} em {path}", code=str(status))

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiResponseError(f"resposta não é JSON em {path}") from exc

        metadata, records = parse_payload(payload)
        return payload, metadata, records
