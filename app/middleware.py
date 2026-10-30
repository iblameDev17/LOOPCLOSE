"""
Request-context middleware for LoopClose.

Responsibilities:
- Accept an inbound X-Request-ID header or generate a fresh 16-hex-char ID.
- Store the ID in the request_id_var ContextVar so it flows into every log record.
- Echo it back as X-Request-ID in the response header.
- Emit a structured http.request log event after every response.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import log_event, request_id_var

logger = logging.getLogger("app.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject a correlation ID and emit access-log events for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        # Resolve or generate a short request ID.
        inbound_id = request.headers.get("X-Request-ID", "")
        rid = inbound_id.strip()[:32] if inbound_id.strip() else uuid.uuid4().hex[:16]

        # Store in ContextVar so all log records in this request carry it.
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000)
            response.headers["X-Request-ID"] = rid
            log_event(
                logger,
                "http.request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        finally:
            request_id_var.reset(token)
