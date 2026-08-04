"""Logging configuration: formatter and handler setup.

This module defines *how* logs look (structured, JSON-ish key=value pairs)
and *where* they go (stdout, for now — a real deployment would ship stdout
to a log aggregator rather than writing files directly).
"""

import logging
import sys
from datetime import UTC, datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Formats log records as single-line structured text.

    Output looks like:
        timestamp=2026-01-15T10:30:00Z level=INFO logger=services.inventory
        message="Asset registered" asset_id=abc-123 correlation_id=req-456

    This is deliberately not raw JSON (easier for a human to read in a
    terminal) but every field is still a clean key=value pair, so it can be
    parsed by a log pipeline with a simple regex or a proper JSON formatter
    swapped in later without changing any calling code.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        base: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Any extra fields passed via logger.info(..., extra={...}) get
        # appended automatically — this is how correlation_id, asset_id,
        # etc. show up without changing this formatter.
        standard_keys = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
            "message",
            "asctime",
        }
        extras = {key: value for key, value in record.__dict__.items() if key not in standard_keys}
        base.update(extras)

        parts = []
        for key, value in base.items():
            if isinstance(value, str) and " " in value:
                parts.append(f'{key}="{value}"')
            else:
                parts.append(f"{key}={value}")

        formatted = " ".join(parts)

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once, at application startup.

    Idempotent: safe to call more than once (e.g. in tests) without
    duplicating handlers.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Avoid attaching duplicate handlers if this is called more than once.
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
