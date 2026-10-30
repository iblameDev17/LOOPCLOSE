"""
Structured JSON logging setup for LoopClose.

Sets up:
- A JSON formatter (one object per line)
- A rotating file handler and a stdout handler
- A ContextVar for the request_id that is injected into every log record
- A redaction filter that masks secret values
- A log_event() helper for emitting typed domain events
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings

# ── Request-ID context variable ───────────────────────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


# ── Filters ───────────────────────────────────────────────────────────────────

_REDACT_KEYS = frozenset(
    {"key", "token", "secret", "password", "authorization", "api_key", "gemini_api_key"}
)
_REDACT_PLACEHOLDER = "***REDACTED***"


class RequestIdFilter(logging.Filter):
    """Inject the current request_id ContextVar value into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class RedactionFilter(logging.Filter):
    """Mask secrets in log records.

    Any LogRecord extra kwarg whose key matches a secret keyword, or whose
    value matches a known secret string, is replaced with ***REDACTED***.
    Prompt/notes content is never logged at all (callers log lengths instead).
    """

    def __init__(self) -> None:
        super().__init__()
        # Build a set of actual secret values at construction time.
        self._secret_values: frozenset[str] = self._collect_secrets()

    @staticmethod
    def _collect_secrets() -> frozenset[str]:
        candidates = {get_settings().gemini_api_key}
        return frozenset(s for s in candidates if s)

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact extra fields on the record dict.
        for key in list(vars(record).keys()):
            if any(k in key.lower() for k in _REDACT_KEYS):
                setattr(record, key, _REDACT_PLACEHOLDER)
            else:
                val = getattr(record, key, None)
                if isinstance(val, str) and val in self._secret_values:
                    setattr(record, key, _REDACT_PLACEHOLDER)
        # Also scrub the message itself.
        if self._secret_values:
            msg = record.getMessage()
            for secret in self._secret_values:
                if secret and secret in msg:
                    record.msg = record.msg.replace(secret, _REDACT_PLACEHOLDER)
                    record.args = None
        return True


# ── JSON formatter ────────────────────────────────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON object (JSON Lines format)."""

    # Fields we copy from the LogRecord into the JSON output.
    _STANDARD_FIELDS = ("level", "logger", "event", "request_id")

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        doc: dict[str, Any] = {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
        }
        # Append any extra fields the caller passed (e.g. item_id, latency_ms …)
        skip = {
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "name",
            "message",
            "taskName",
            "request_id",
            "event",
        }
        for key, val in vars(record).items():
            if key not in skip and not key.startswith("_"):
                doc[key] = val

        if record.exc_info:
            doc["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(doc, default=str, ensure_ascii=False)


# ── Handler factory ───────────────────────────────────────────────────────────


def _make_handlers() -> list[logging.Handler]:
    fmt = JsonFormatter()
    request_filter = RequestIdFilter()
    redact_filter = RedactionFilter()

    handlers: list[logging.Handler] = []

    # Rotating file handler (5 MB × 3 backups)
    log_path = get_settings().log_file
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.addFilter(request_filter)
    fh.addFilter(redact_filter)
    handlers.append(fh)

    # Stdout handler (Render reads stdout in its log viewer)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.addFilter(request_filter)
    sh.addFilter(redact_filter)
    handlers.append(sh)

    return handlers


def configure_logging() -> None:
    """Configure the root logger and all app.* loggers.  Call once at startup."""
    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)

    root = logging.getLogger()
    # Avoid adding duplicate handlers if called more than once (e.g. in tests).
    if root.handlers:
        return

    root.setLevel(level)
    for handler in _make_handlers():
        root.addHandler(handler)

    # Quieten noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# ── log_event() helper ────────────────────────────────────────────────────────


_RESERVED_LOGRECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
    }
)


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit a structured domain event as a log record.

    Usage:
        log_event(logger, "item.closed", item_id=12, outcome_type="completed")

    The ``event`` value becomes the ``event`` field in the JSON output.
    All keyword arguments are added as extra fields (no content, no secrets).
    """
    exc_info = fields.pop("exc_info", None)
    safe_fields = {}
    for k, v in fields.items():
        if k in _RESERVED_LOGRECORD_ATTRS:
            safe_fields["detail" if k == "message" else f"field_{k}"] = v
        else:
            safe_fields[k] = v
    extra = {"event": event, **safe_fields}
    logger.log(level, event, exc_info=exc_info, extra=extra)
