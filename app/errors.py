"""
Custom exceptions and global error handlers for LoopClose.

All application-level errors are raised as one of the custom exceptions here.
The global handlers convert them to:
  - A Jinja2 HTML error page (with request ID) for browser requests.
  - An HX-Trigger toast partial for HTMX requests (non-fatal warnings).
  - A structured JSON error object for /api/v1 requests.

A raw traceback is never allowed to reach the user.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import log_event, request_id_var

logger = logging.getLogger("app.system")

# Templates are configured in main.py; we reference the same directory.
# We initialise lazily to avoid import-order issues.
_templates: Jinja2Templates | None = None


def _get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory="app/templates")
    return _templates


# ── Custom exceptions ─────────────────────────────────────────────────────────


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found.") -> None:
        self.message = message
        super().__init__(message)


class ValidationFailed(Exception):
    """Raised when business-rule validation fails (HTTP 422)."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)


class InvalidTransitionError(Exception):
    """Raised when a state-machine transition is not permitted (HTTP 409)."""

    def __init__(self, message: str = "That state change is not allowed.") -> None:
        self.message = message
        super().__init__(message)


class AIUnavailableError(Exception):
    """Internal signal that AI is unavailable; callers use the fallback instead.
    This must never surface as an HTTP 500.
    """

    def __init__(self, reason: str = "AI service unavailable.") -> None:
        self.reason = reason
        super().__init__(reason)


# ── Response helpers ──────────────────────────────────────────────────────────


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _is_api(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def _json_error(
    code: str,
    message: str,
    request_id: str,
    status: int,
    details: list[dict] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "details": details or [],
            }
        },
    )


def _html_error(request: Request, status: int, title: str, message: str) -> HTMLResponse:
    rid = request_id_var.get("-")
    templates = _get_templates()
    context = {
        "request": request,
        "status": status,
        "title": title,
        "message": message,
        "request_id": rid,
    }
    html = templates.TemplateResponse(request=request, name="error.html", context=context)
    html.status_code = status
    return html


# ── Global handlers ───────────────────────────────────────────────────────────


async def handle_not_found(request: Request, exc: NotFoundError) -> HTMLResponse | JSONResponse:
    rid = request_id_var.get("-")
    log_event(
        logger,
        "http.error",
        level=logging.WARNING,
        status=404,
        path=str(request.url.path),
        message=exc.message,
    )
    if _is_api(request):
        return _json_error("not_found", exc.message, rid, 404)
    return _html_error(request, 404, "We can't find that", exc.message)


async def handle_validation_failed(
    request: Request, exc: ValidationFailed
) -> HTMLResponse | JSONResponse:
    rid = request_id_var.get("-")
    details = [{"field": exc.field, "issue": exc.message}] if exc.field else []
    log_event(
        logger,
        "http.error",
        level=logging.WARNING,
        status=422,
        path=str(request.url.path),
        message=exc.message,
    )
    if _is_api(request):
        return _json_error("validation_error", exc.message, rid, 422, details)
    return _html_error(request, 422, "Invalid input", exc.message)


async def handle_invalid_transition(
    request: Request, exc: InvalidTransitionError
) -> HTMLResponse | JSONResponse:
    rid = request_id_var.get("-")
    log_event(
        logger,
        "http.error",
        level=logging.WARNING,
        status=409,
        path=str(request.url.path),
        message=exc.message,
    )
    if _is_api(request):
        return _json_error("invalid_transition", exc.message, rid, 409)
    return _html_error(request, 409, "Action not allowed", exc.message)


async def handle_generic_error(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    rid = request_id_var.get("-")
    log_event(
        logger,
        "app.error",
        level=logging.ERROR,
        status=500,
        path=str(request.url.path),
        exc_type=type(exc).__name__,
        exc_info=True,
    )
    if _is_api(request):
        return _json_error("internal_error", "An unexpected error occurred.", rid, 500)
    return _html_error(
        request,
        500,
        "Something went wrong",
        "An unexpected error occurred. Please try again or contact support.",
    )


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> HTMLResponse | JSONResponse:
    rid = request_id_var.get("-")
    level = logging.WARNING if exc.status_code < 500 else logging.ERROR
    log_event(
        logger,
        "http.error",
        level=level,
        status=exc.status_code,
        path=str(request.url.path),
        message=str(exc.detail),
    )
    if _is_api(request):
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _json_error(code, str(exc.detail), rid, exc.status_code)
    title = "We can't find that" if exc.status_code == 404 else f"Error {exc.status_code}"
    return _html_error(request, exc.status_code, title, str(exc.detail))
