"""Download de arquivos publicados fora da API."""

import httpx

from world_bank.exceptions import SourceFileError

# Todo .xlsx é um arquivo zip, e começa com estes bytes.
_XLSX_SIGNATURE = b"PK"


def download_xlsx(url: str, timeout: float) -> bytes:
    """Baixa um arquivo ``.xlsx``.

    Args:
        url: Endereço do arquivo.
        timeout: Tempo máximo da requisição, em segundos.

    Returns:
        Os bytes do arquivo, sem alteração.

    Raises:
        SourceFileError: Se o download falhar ou a resposta não for um ``.xlsx``
            (por exemplo, uma página de erro em HTML).
    """
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SourceFileError(f"falha ao baixar {url}: {exc}") from exc
    if not response.content.startswith(_XLSX_SIGNATURE):
        raise SourceFileError(f"a resposta de {url} não é um arquivo .xlsx")
    return response.content
