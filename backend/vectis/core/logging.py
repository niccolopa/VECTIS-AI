"""Structured logging via structlog.

In development we render human-friendly console logs; in production (or when
``VECTIS_LOG_JSON=true``) we emit JSON lines suitable for log aggregation. Use
``get_logger(__name__)`` everywhere instead of the stdlib logger directly so
that every log line carries structured, queryable context.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from vectis.core.config import get_settings

_configured = False


def configure_logging() -> None:
    """Configure structlog + stdlib logging once, idempotently."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger, configuring logging on first use."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
