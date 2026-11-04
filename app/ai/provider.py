"""LLM provider protocol — all providers implement this interface.

Services never call providers directly; they use AIClient (app/ai/client.py).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for an LLM backend."""

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema_hint: str,
        timeout: int,
    ) -> str:
        """Send a prompt and return a JSON string.

        Raises on network/timeout errors so the caller (AIClient) can retry.
        """
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts (Unit 9)."""
        ...
