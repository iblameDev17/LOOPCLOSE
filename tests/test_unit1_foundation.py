"""
Unit 1 tests — Foundation.

Covers:
- /health returns 200 with db: ok
- X-Request-ID is returned in response headers
- An echoed inbound X-Request-ID appears in the response header
- Redaction filter masks secret values
- DATABASE_URL normalisation (postgres:// and postgresql:// -> postgresql+psycopg://)
"""

from __future__ import annotations

import logging

# ── /health ───────────────────────────────────────────────────────────────────


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_db_ok(client):
    data = client.get("/health").json()
    assert data["db"] == "ok"


def test_health_shape(client):
    data = client.get("/health").json()
    assert "status" in data
    assert "app" in data
    assert "env" in data
    assert "db" in data
    assert "ai" in data
    assert "provider" in data["ai"]
    assert "configured" in data["ai"]


def test_health_ai_provider_reflected(client):
    """Provider field reflects current LLM_PROVIDER env setting."""
    data = client.get("/health").json()
    assert data["ai"]["provider"] in ("fake", "gemini")


# ── Request-ID header ─────────────────────────────────────────────────────────


def test_request_id_header_present(client):
    """Every response must include X-Request-ID."""
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_request_id_echoed(client):
    """If the client sends X-Request-ID, the server echoes it back unchanged."""
    custom_id = "test-rid-abc123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("x-request-id") == custom_id


def test_request_id_generated_when_absent(client):
    """If no X-Request-ID is sent, the server generates one (non-empty string)."""
    response = client.get("/health")
    rid = response.headers.get("x-request-id", "")
    assert len(rid) > 0


# ── Redaction filter ──────────────────────────────────────────────────────────


def test_redaction_filter_masks_key_names():
    """Log records whose extra keys match secret patterns should be masked."""
    from app.logging_config import RedactionFilter

    filt = RedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.api_key = "super-secret-value"  # type: ignore[attr-defined]
    filt.filter(record)
    assert record.api_key == "***REDACTED***"  # type: ignore[attr-defined]


def test_redaction_filter_masks_secret_values():
    """A known secret value appearing in any field should be masked."""
    import os as _os
    from importlib import reload

    import app.config as cfg_mod
    import app.logging_config as log_mod

    # Temporarily set a fake key so the filter knows what to mask.
    _os.environ["GEMINI_API_KEY"] = "my-fake-key-xyz"

    # Reset lru_cache so Settings re-reads env.
    cfg_mod.get_settings.cache_clear()
    reload(log_mod)

    filt = log_mod.RedactionFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="my-fake-key-xyz is logged",
        args=(),
        exc_info=None,
    )
    record.request_id = "-"  # type: ignore[attr-defined]
    filt.filter(record)
    assert "my-fake-key-xyz" not in record.msg

    # Clean up
    del _os.environ["GEMINI_API_KEY"]
    cfg_mod.get_settings.cache_clear()
    reload(log_mod)


# ── DATABASE_URL normalisation ────────────────────────────────────────────────


def test_url_normalisation_postgres_scheme():
    """postgres:// -> postgresql+psycopg://"""
    from app.config import Settings

    s = Settings(database_url="postgres://user:pass@host/db")
    assert s.database_url.startswith("postgresql+psycopg://")


def test_url_normalisation_postgresql_scheme():
    """postgresql:// -> postgresql+psycopg://"""
    from app.config import Settings

    s = Settings(database_url="postgresql://user:pass@host/db")
    assert s.database_url.startswith("postgresql+psycopg://")


def test_url_no_change_for_sqlite():
    """sqlite:// URLs must not be altered."""
    from app.config import Settings

    s = Settings(database_url="sqlite:///./local.db")
    assert s.database_url == "sqlite:///./local.db"


def test_url_no_change_for_already_normalised():
    """Already-normalised URLs must be left alone."""
    from app.config import Settings

    url = "postgresql+psycopg://user:pass@host/db"
    s = Settings(database_url=url)
    assert s.database_url == url


# ── Dashboard renders ─────────────────────────────────────────────────────────


def test_dashboard_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"LoopClose" in response.content


def test_dashboard_contains_nav(client):
    response = client.get("/")
    assert b"nav" in response.content.lower()


# ── Error page handling ───────────────────────────────────────────────────────


def test_404_renders_error_page_with_request_id(client):
    response = client.get("/nonexistent-page-xyz")
    assert response.status_code == 404
    assert b"error-request-id" in response.content
    assert "x-request-id" in response.headers


def test_404_api_returns_json(client):
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert response.headers.get("content-type", "").startswith("application/json")
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"
    assert "request_id" in data["error"]
