"""Structured logging (foundation issue 1.7).

JSON logs on stderr and (optionally) a rotating file, with a correlation ID
contextvar so a single task run's traffic can be stitched together across
agents and into the evidence trace. Persistence to the context store is added
by the store itself in foundation issue 1.4 (it registers a log handler).

This module must stay dependency-light (stdlib + structlog only) because the
configuration system imports it.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Literal

import structlog

CorrelationId = str

_CORRELATION_KEY = "correlation_id"


def new_correlation_id() -> CorrelationId:
    """Start a new correlation scope and bind it to the current context."""
    import uuid

    cid = uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(**{_CORRELATION_KEY: cid})
    return cid


def set_correlation_id(correlation_id: CorrelationId) -> None:
    """Adopt an existing correlation ID (e.g. a specialist adopting its task's ID)."""
    structlog.contextvars.bind_contextvars(**{_CORRELATION_KEY: correlation_id})


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to `name`."""
    return structlog.get_logger(name)


def configure_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    json_format: bool = True,
    file_path: str | None = None,
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> None:
    """Configure structlog + stdlib handlers. Safe to call repeatedly."""
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json_format else structlog.dev.ConsoleRenderer()
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
        ],
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    if file_path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler: logging.Handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
