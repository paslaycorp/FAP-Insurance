"""
FAP-Insurance — Structured Logging
structlog → JSON. request_id propagation via contextvars.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

from config import SETTINGS

# ── Context variable for request_id ─────────────────────────
_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _REQUEST_ID.get()


def set_request_id(req_id: str) -> None:
    _REQUEST_ID.set(req_id)


def clear_request_id() -> None:
    _REQUEST_ID.set("")


# ── Configure structlog ─────────────────────────────────────

def _configure() -> None:
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if SETTINGS.LOG_JSON:
        shared_processors.append(structlog.processors.dict_tracebacks)
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [formatter],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, SETTINGS.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also patch stdlib logging so third-party libs emit structlog format
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, SETTINGS.LOG_LEVEL.upper(), logging.INFO),
    )


_configure()

# ── Public logger ───────────────────────────────────────────
log = structlog.get_logger()
