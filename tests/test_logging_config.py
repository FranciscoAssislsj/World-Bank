import logging

from world_bank.logging_config import LOG_FORMAT, StructuredFormatter, configure_logging


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "world_bank.test", logging.INFO, __file__, 1, "page fetched", None, None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_appends_extra_fields_sorted() -> None:
    formatter = StructuredFormatter("%(message)s")

    line = formatter.format(_record(page=2, indicator="SP.POP.TOTL"))

    assert line == "page fetched | indicator=SP.POP.TOTL page=2"


def test_formatter_without_extra_fields() -> None:
    formatter = StructuredFormatter("%(levelname)s %(message)s")

    assert formatter.format(_record()) == "INFO page fetched"


def test_configure_logging_does_not_duplicate_handlers() -> None:
    configure_logging("WARNING")
    configure_logging("DEBUG")

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    handler = root.handlers[0]
    assert isinstance(handler.formatter, StructuredFormatter)
    assert handler.formatter._fmt == LOG_FORMAT
