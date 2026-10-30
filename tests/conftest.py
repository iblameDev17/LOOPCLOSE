"""
Test fixtures shared across all test modules.

- Temporary SQLite database per session.
- FastAPI TestClient with the full app.
- LLM_PROVIDER forced to "fake" via env override so no real LLM is called.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force fake provider and test DB before importing app modules.
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(scope="session")
def temp_db_path(tmp_path_factory):
    """Create a temporary SQLite DB file for the test session."""
    db_dir = tmp_path_factory.mktemp("db")
    return str(db_dir / "test.db")


@pytest.fixture(scope="session")
def test_app(temp_db_path):
    """Return a configured FastAPI app instance using the temp DB."""
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path}"
    # Import app after env is set so Settings picks it up.
    from app.main import create_app

    application = create_app()
    return application


@pytest.fixture(scope="session")
def client(test_app):
    """Return a TestClient for the app."""
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c
