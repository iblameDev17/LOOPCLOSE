"""Deterministic fallback extractors for when AI is unavailable.

Each function provides a best-effort extraction from raw text using
simple pattern matching — no LLM, no network.
"""

from __future__ import annotations

import re


def heuristic_recap(raw_notes: str) -> dict:
    """Extract a basic recap from raw notes using prefix-matching rules.

    Returns a dict matching the RecapResult schema with whatever can be parsed.
    Per ARCHITECTURE.md §10.3:
      - Lines starting with Action:/TODO/- [ ]/AI: → action items (no owner/due)
      - Lines starting with Decision: → decisions
      - First 2 sentences → summary
    """
    lines = raw_notes.strip().splitlines()
    action_items: list[dict] = []
    decisions: list[dict] = []
    open_questions: list[str] = []
    regular_lines: list[str] = []

    # Patterns for action items
    action_patterns = [
        re.compile(r"^\s*(?:action\s*:)\s*(.+)", re.IGNORECASE),
        re.compile(r"^\s*(?:TODO\s*:?)\s*(.+)", re.IGNORECASE),
        re.compile(r"^\s*-\s*\[\s*\]\s*(.+)"),
        re.compile(r"^\s*(?:AI\s*:)\s*(.+)", re.IGNORECASE),
    ]
    decision_pattern = re.compile(r"^\s*(?:decision\s*:)\s*(.+)", re.IGNORECASE)
    question_pattern = re.compile(r"^\s*(?:question\s*:|\?\s*)\s*(.+)", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check decisions first
        m = decision_pattern.match(stripped)
        if m:
            text = m.group(1).strip()
            if len(text) >= 3:
                decisions.append({"text": text})
            continue

        # Check action items
        matched = False
        for pat in action_patterns:
            m = pat.match(stripped)
            if m:
                title = m.group(1).strip()
                if len(title) >= 3:
                    action_items.append(
                        {
                            "title": title[:200],
                            "owner_name": None,
                            "due_date": None,
                            "priority": "medium",
                            "rationale": None,
                        }
                    )
                matched = True
                break

        if matched:
            continue

        # Check open questions
        m = question_pattern.match(stripped)
        if m:
            open_questions.append(m.group(1).strip())
            continue
        if stripped.endswith("?"):
            open_questions.append(stripped)
            continue

        regular_lines.append(stripped)

    # Summary: first 2 sentences from regular lines
    summary = ""
    if regular_lines:
        joined = " ".join(regular_lines)
        # Split on sentence-ending punctuation
        sentences = re.split(r"(?<=[.!?])\s+", joined)
        summary = ". ".join(sentences[:2])
        if summary and not summary.endswith("."):
            summary += "."
        # Cap at ~120 words
        words = summary.split()
        if len(words) > 120:
            summary = " ".join(words[:120]) + "…"

    return {
        "summary": summary,
        "decisions": decisions,
        "action_items": action_items,
        "open_questions": open_questions,
    }
