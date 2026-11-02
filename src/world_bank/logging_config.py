"""Configuração única de logging, com contexto estruturado em ``chave=valor``."""

import logging
import sys

_STANDARD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
}

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class StructuredFormatter(logging.Formatter):
    """Acrescenta à mensagem os campos passados em ``extra=`` como ``chave=valor``.

    Exemplo: ``logger.info("page fetched", extra={"page": 2})`` gera
    ``... page fetched | page=2``.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formata o registro e anexa os campos extras em ordem alfabética.

        Args:
            record: Registro de log.

        Returns:
            Linha de log formatada.
        """
        base = super().format(record)
        extras = {
            key: value
            for key, value in vars(record).items()
            if key not in _STANDARD_ATTRS and not key.startswith("_")
        }
        if not extras:
            return base
        context = " ".join(f"{key}={value}" for key, value in sorted(extras.items()))
        return f"{base} | {context}"


def configure_logging(level: str = "INFO") -> None:
    """Configura o logger raiz (chamar uma única vez, no ponto de entrada).

    Chamadas repetidas substituem o handler anterior em vez de duplicá-lo.

    Args:
        level: Nível mínimo de log (ex.: ``"INFO"``).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredFormatter(LOG_FORMAT))
    logging.basicConfig(level=level, handlers=[handler], force=True)
