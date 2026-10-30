"""
Health check router.

GET /health returns a JSON snapshot of the application's state used by:
- The GitHub Actions smoke test (checks .commit == pushed SHA)
- Render's health-check ping (returns non-200 on DB failure → 503)
- Manual diagnostics
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> JSONResponse:
    """Return application health.  DB failure → HTTP 503 (degraded).
    AI being unconfigured does NOT degrade health — the app still works via fallbacks.
    """
    db_ok = check_db()

    payload = {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "env": settings.app_env,
        "commit": settings.commit_sha or None,
        "db": "ok" if db_ok else "error",
        "ai": {
            "provider": settings.llm_provider,
            "configured": settings.ai_configured,
        },
    }

    status_code = 200 if db_ok else 503
    return JSONResponse(content=payload, status_code=status_code)
