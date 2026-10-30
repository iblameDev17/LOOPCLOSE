"""
SQLAlchemy engine, session, Base and the FastAPI dependency for DB access.

Uses sync sessions throughout (routes call services via threadpool — perfectly
fine for this scale and keeps the code simple).
"""

from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _build_connect_args() -> dict:
    """SQLite needs check_same_thread=False; Postgres does not."""
    if settings.is_sqlite:
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    settings.database_url,
    connect_args=_build_connect_args(),
    echo=False,
)

# Enable WAL mode for SQLite to allow concurrent reads during writes.
if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_wal(dbapi_conn, _connection_record):  # type: ignore[misc]
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base.  All models inherit from this."""


def get_db():
    """FastAPI dependency that yields a database session and closes it afterward."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    """Run a trivial query to verify the database connection.  Used by /health."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
