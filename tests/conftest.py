"""
Test fixtures shared across all test modules.

- Temporary SQLite database per test session.
- FastAPI TestClient with the full app.
- LLM_PROVIDER forced to "fake" via env override so no real LLM is called.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Force test environment and temporary DB file before any app imports
_temp_dir = tempfile.gettempdir()
_test_db_file = os.path.join(_temp_dir, f"loopclose_test_{os.getpid()}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_file}"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["APP_ENV"] = "test"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def test_app():
    """Return a configured FastAPI app instance using the temp DB."""
    Base.metadata.create_all(bind=engine)
    application = create_app()
    return application


@pytest.fixture(scope="session")
def client(test_app):
    """Return a TestClient for the app."""
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db_session(test_app):
    """Provide a DB session for unit tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure database tables are clean between tests."""
    Base.metadata.create_all(bind=engine)
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
