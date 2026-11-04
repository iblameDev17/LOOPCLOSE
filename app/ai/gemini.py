"""Gemini provider using the google-genai SDK (v2.34+).

Verified against the installed SDK: google.genai 2.34.0
Uses Client.models.generate_content with response_mime_type='application/json'.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger("app.ai")


class GeminiProvider:
    """LLM provider backed by the Gemini API via google-genai SDK."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._embedding_model = settings.embedding_model

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema_hint: str,
        timeout: int,
    ) -> str:
        """Call Gemini and return the raw JSON string from the model."""
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=4096,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts (Unit 9)."""
        response = self._client.models.embed_content(
            model=self._embedding_model,
            contents=texts,
        )
        return [e.values for e in response.embeddings]
