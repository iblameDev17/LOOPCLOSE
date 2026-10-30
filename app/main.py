"""
FastAPI application factory for LoopClose.

This module:
- Configures structured logging before anything else.
- Creates the FastAPI app instance.
- Mounts static files and configures Jinja2 templates.
- Registers all routers.
- Registers global error handlers.
- Adds the request-context middleware.
- On startup: creates all DB tables, emits app.startup event, optionally seeds demo data.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine
from app.errors import (
    InvalidTransitionError,
    NotFoundError,
    ValidationFailed,
    handle_generic_error,
    handle_http_exception,
    handle_invalid_transition,
    handle_not_found,
    handle_validation_failed,
)
from app.logging_config import configure_logging, log_event
from app.middleware import RequestContextMiddleware
from app.routers import health, web_dashboard, web_meetings, web_people

# Configure logging as the very first thing (before any other imports log).
configure_logging()

logger = logging.getLogger("app.system")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Create all tables (idempotent; no Alembic for this project).
    Base.metadata.create_all(bind=engine)

    log_event(
        logger,
        "app.startup",
        env=settings.app_env,
        db_dialect="sqlite" if settings.is_sqlite else "postgresql",
        ai_provider=settings.llm_provider,
        ai_configured=settings.ai_configured,
        # Never log the actual key — only whether it is set.
    )

    if settings.seed_demo_data:
        _seed()

    yield


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware (outermost first) ──────────────────────────────────────
    app.add_middleware(RequestContextMiddleware)

    # ── Static files ──────────────────────────────────────────────────────
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # ── Templates (shared; also instantiated per-router for convenience) ──
    Jinja2Templates(directory="app/templates")

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(web_dashboard.router)
    app.include_router(web_people.router)
    app.include_router(web_meetings.router)
    # Additional routers added in later units (items, kb, nudges …)

    # ── Error handlers ────────────────────────────────────────────────────
    app.add_exception_handler(NotFoundError, handle_not_found)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationFailed, handle_validation_failed)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidTransitionError, handle_invalid_transition)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_generic_error)  # type: ignore[arg-type]

    return app


def _seed() -> None:
    """Seed the database with demo data if empty.  Implemented in Unit 8."""
    log_event(logger, "app.seeded", note="seed hook called — script not implemented yet (Unit 8)")


app = create_app()
