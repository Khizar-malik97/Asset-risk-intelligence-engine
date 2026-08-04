"""Public logging entrypoint used throughout the application.

Usage:
    from logging_.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Asset registered", extra={"asset_id": asset.id})
"""

import logging

from config.settings import get_settings
from logging_.config import configure_logging

_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name.

    Configures the root logger (formatter, level, handler) on first call
    only, using the log level from application settings. Every subsequent
    call just returns a standard, correctly-configured logger instance.
    """
    global _configured
    if not _configured:
        settings = get_settings()
        configure_logging(level=settings.log_level)
        _configured = True

    return logging.getLogger(name)
