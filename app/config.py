"""
Application configuration.

All settings are read from environment variables (or a .env file at project root).
This is the ONLY place that reads os.environ — all other modules import `settings`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    app_env: str = "local"
    app_name: str = "LoopClose"

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./local.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        """Render injects a postgres:// or postgresql:// URL.  SQLAlchemy 2.x
        with psycopg 3 requires the scheme postgresql+psycopg://."""
        if isinstance(v, str):
            if v.startswith("postgres://"):
                v = "postgresql+psycopg://" + v[len("postgres://") :]
            elif v.startswith("postgresql://"):
                v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    # ── AI / LLM ──────────────────────────────────────────────────────────
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = ""
    embedding_model: str = ""
    ai_timeout_seconds: int = 25
    ai_max_retries: int = 1
    ai_max_input_chars: int = 12000

    # ── Retrieval ─────────────────────────────────────────────────────────
    retriever: str = "llm"

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # ── Demo data ─────────────────────────────────────────────────────────
    seed_demo_data: bool = False

    # ── Server ────────────────────────────────────────────────────────────
    port: int = 8000

    # ── Deployment (set by Render at runtime) ─────────────────────────────
    render_git_commit: str = ""
    git_sha: str = ""

    @property
    def commit_sha(self) -> str:
        """Return the deployed commit SHA from whichever var is set."""
        return self.render_git_commit or self.git_sha or ""

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key) and self.llm_provider == "gemini"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.  Import and call this everywhere."""
    return Settings()


settings = get_settings()
