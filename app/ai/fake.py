"""Fake LLM provider for tests — deterministic, no network.

Supports switchable failure modes: timeout, invalid JSON, empty response.
All tests MUST use this provider (AGENTS.md §6.8, §9).
"""

from __future__ import annotations

import json
import re

_RECAP_RESPONSE = {
    "summary": "Team discussed project timeline and blockers. Key decisions were made about deployment.",
    "decisions": [{"text": "Deploy to production by end of week"}],
    "action_items": [
        {
            "title": "Update deployment scripts",
            "owner_name": None,
            "due_date": None,
            "priority": "medium",
            "rationale": "Needed for production release",
        }
    ],
    "open_questions": ["What is the rollback plan?"],
}

_BRIEF_RESPONSE = {
    "tldr": "Project meeting covered deployment timelines and blockers.",
    "key_decisions": ["Deploy to production by end of week"],
    "your_items": ["Update deployment scripts (due: TBD)"],
    "changed_since": [],
    "open_questions": ["What is the rollback plan?"],
    "related_knowledge": [],
    "suggested_first_steps": ["Review deployment scripts"],
}

_KB_SUMMARIZE_RESPONSE = {
    "summary": "Overview of deployment architecture and system requirements.",
    "tags": ["deployment", "architecture", "infra"],
}


class FakeProvider:
    """Deterministic provider for testing with switchable failure modes."""

    def __init__(self) -> None:
        self.fail_mode: str | None = None  # "timeout", "invalid_json", "empty"
        self.call_count: int = 0
        self.last_system: str = ""
        self.last_prompt: str = ""

    def set_fail_mode(self, mode: str | None) -> None:
        """Set the failure mode: 'timeout', 'invalid_json', 'empty', or None."""
        self.fail_mode = mode

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema_hint: str,
        timeout: int,
    ) -> str:
        """Return canned JSON or simulate failure based on fail_mode."""
        self.call_count += 1
        self.last_system = system
        self.last_prompt = prompt

        if self.fail_mode == "timeout":
            raise TimeoutError("Simulated timeout")
        if self.fail_mode == "invalid_json":
            return "this is not valid json {{"
        if self.fail_mode == "empty":
            return ""

        # Determine which operation based on schema_hint
        if "RecapResult" in schema_hint:
            return json.dumps(_RECAP_RESPONSE)
        if "BriefResult" in schema_hint:
            return json.dumps(_BRIEF_RESPONSE)
        if "KBSummarizeResult" in schema_hint:
            return json.dumps(_KB_SUMMARIZE_RESPONSE)
        if "LinkResult" in schema_hint:
            # Extract document IDs from the prompt if present
            doc_ids = [int(m) for m in re.findall(r'"id":\s*(\d+)', prompt)]
            if not doc_ids:
                doc_ids = [1]
            matches = [
                {
                    "document_id": d_id,
                    "relevance": 0.88,
                    "reason": "Direct architectural and context match",
                }
                for d_id in doc_ids[:2]
            ]
            return json.dumps({"matches": matches})

        # Generic fallback
        return json.dumps({"summary": "AI generated content", "items": []})

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return fake embedding vectors of dimension 768."""
        return [[0.1] * 768 for _ in texts]
