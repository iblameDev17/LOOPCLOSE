"""AIClient — the single entry point for all AI operations.

Services call AIClient.run_structured(); never a vendor SDK directly.
The client handles truncation, timeout, code-fence stripping, JSON parsing,
Pydantic validation, retries, and structured logging.  It never raises for
AI problems — callers inspect ``AIResult.ok`` and use a fallback.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.provider import LLMProvider
from app.config import get_settings
from app.logging_config import log_event

logger = logging.getLogger("app.ai")

T = TypeVar("T", bound=BaseModel)


@dataclass
class AIResult[T: BaseModel]:
    """Result of an AI operation.  Callers check ``ok`` before using ``data``."""

    ok: bool
    data: T | None = None
    error_code: str | None = None
    latency_ms: int = 0
    attempts: int = 0
    raw_text: str = ""


# ── Code-fence stripping ──────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON output."""
    text = text.strip()
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


# ── Provider factory ──────────────────────────────────────────────────────────

_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the singleton provider instance, creating it on first call."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()

    if settings.llm_provider == "fake":
        from app.ai.fake import FakeProvider

        _provider_instance = FakeProvider()
        return _provider_instance

    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        from app.ai.gemini import GeminiProvider

        _provider_instance = GeminiProvider()
        return _provider_instance

    # No API key — warn once; callers will get AIResult(ok=False)
    logger.warning(
        "No AI provider configured (LLM_PROVIDER=%s, key set=%s). AI features will use fallbacks.",
        settings.llm_provider,
        bool(settings.gemini_api_key),
    )
    return None  # type: ignore[return-value]


def reset_provider() -> None:
    """Reset the cached provider (useful for tests)."""
    global _provider_instance
    _provider_instance = None


# ── Main client ───────────────────────────────────────────────────────────────


class AIClient:
    """Unified AI client used by all services."""

    @staticmethod
    def run_structured(
        operation: str,
        *,
        system: str,
        prompt: str,
        model_cls: type[T],
        prompt_version: str = "",
    ) -> AIResult[T]:
        """Send a prompt, parse and validate the JSON response.

        Returns AIResult(ok=True, data=...) on success; AIResult(ok=False, ...)
        on any failure — **never raises for AI problems**.
        """
        settings = get_settings()
        provider = get_provider()

        if provider is None:
            log_event(
                logger,
                "ai.fallback",
                level=logging.WARNING,
                operation=operation,
                reason="no_provider",
                fallback="heuristic",
            )
            return AIResult(ok=False, error_code="no_provider")

        # Truncate input if too long
        max_chars = settings.ai_max_input_chars
        if len(prompt) > max_chars:
            log_event(
                logger,
                "ai.truncated_input",
                level=logging.WARNING,
                operation=operation,
                original_chars=len(prompt),
                truncated_to=max_chars,
            )
            prompt = prompt[:max_chars]

        max_retries = settings.ai_max_retries
        timeout = settings.ai_timeout_seconds
        schema_hint = model_cls.__name__

        start = time.monotonic()
        attempts = 0
        last_error = ""

        for attempt in range(1 + max_retries):
            attempts += 1
            try:
                # Add JSON-only reminder on retries
                effective_system = system
                if attempt > 0:
                    effective_system += (
                        "\n\nIMPORTANT: Your previous response was not valid JSON. "
                        "Return ONLY valid JSON matching the schema. No prose, no code fences."
                    )

                raw = provider.generate_json(
                    system=effective_system,
                    prompt=prompt,
                    schema_hint=schema_hint,
                    timeout=timeout,
                )

                if not raw or not raw.strip():
                    last_error = "empty_response"
                    continue

                # Strip code fences
                cleaned = _strip_fences(raw)

                # Parse JSON
                try:
                    parsed = json.loads(cleaned)
                except json.JSONDecodeError:
                    last_error = "invalid_json"
                    continue

                # Validate with Pydantic
                try:
                    data = model_cls.model_validate(parsed)
                except ValidationError:
                    last_error = "validation_error"
                    continue

                latency = int((time.monotonic() - start) * 1000)
                outcome = "success" if attempts == 1 else "retry_success"

                log_event(
                    logger,
                    "ai.call",
                    operation=operation,
                    provider=settings.llm_provider,
                    model=settings.gemini_model,
                    prompt_version=prompt_version,
                    latency_ms=latency,
                    attempts=attempts,
                    outcome=outcome,
                    input_chars=len(prompt),
                    output_chars=len(raw),
                )

                return AIResult(
                    ok=True,
                    data=data,
                    latency_ms=latency,
                    attempts=attempts,
                    raw_text=raw,
                )

            except TimeoutError:
                last_error = "timeout"
                continue
            except Exception as exc:
                last_error = f"provider_error:{type(exc).__name__}"
                continue

        # All attempts failed
        latency = int((time.monotonic() - start) * 1000)

        log_event(
            logger,
            "ai.call",
            operation=operation,
            provider=settings.llm_provider,
            model=settings.gemini_model,
            prompt_version=prompt_version,
            latency_ms=latency,
            attempts=attempts,
            outcome="error",
            error_code=last_error,
            input_chars=len(prompt),
            output_chars=0,
        )
        log_event(
            logger,
            "ai.fallback",
            level=logging.WARNING,
            operation=operation,
            reason=last_error,
            fallback="heuristic",
        )

        return AIResult(
            ok=False,
            error_code=last_error,
            latency_ms=latency,
            attempts=attempts,
        )
