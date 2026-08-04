"""Unit tests for the logging framework."""

import logging

from logging_.config import StructuredFormatter, configure_logging
from logging_.logger import get_logger


def test_structured_formatter_includes_core_fields():
    """Formatted output must include timestamp, level, logger, and message."""
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Something happened",
        args=(),
        exc_info=None,
    )
    formatter = StructuredFormatter()

    output = formatter.format(record)

    assert "level=INFO" in output
    assert "logger=test.module" in output
    assert 'message="Something happened"' in output
    assert "timestamp=" in output


def test_structured_formatter_includes_extra_fields():
    """Extra fields passed via `extra={}` must appear in the output."""
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Asset registered",
        args=(),
        exc_info=None,
    )
    record.asset_id = "abc-123"
    record.correlation_id = "req-456"
    formatter = StructuredFormatter()

    output = formatter.format(record)

    assert "asset_id=abc-123" in output
    assert "correlation_id=req-456" in output


def test_configure_logging_is_idempotent():
    """Calling configure_logging() multiple times must not duplicate handlers."""
    configure_logging(level="INFO")
    handler_count_after_first = len(logging.getLogger().handlers)

    configure_logging(level="INFO")
    handler_count_after_second = len(logging.getLogger().handlers)

    assert handler_count_after_first == handler_count_after_second


def test_get_logger_returns_standard_logger_instance():
    """get_logger() must return a usable, correctly-named stdlib Logger."""
    logger = get_logger("test.some_module")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.some_module"


def test_get_logger_output_is_captured(caplog):
    """A log call through get_logger() must produce a record at the correct
    level, with the correct message and extra fields attached.

    Uses pytest's `caplog` fixture rather than `capsys`: caplog attaches its
    own handler directly to the logger and captures LogRecord objects, so it
    isn't affected by which physical stdout stream our own handler happened
    to bind to when logging was first configured.
    """
    logger = get_logger("test.capture_check")

    with caplog.at_level(logging.WARNING, logger="test.capture_check"):
        logger.warning("Disk space low", extra={"available_mb": 512})

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "WARNING"
    assert record.message == "Disk space low"
    assert record.available_mb == 512
