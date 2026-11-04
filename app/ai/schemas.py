"""Pydantic output schemas for AI operations.

These models validate the JSON returned by the LLM before it enters the app.
They are separate from the DB schemas to keep the AI boundary clean.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RecapActionItem(BaseModel):
    """A single action item extracted by AI from meeting notes."""

    title: str = Field(..., min_length=1, max_length=200)
    owner_name: str | None = None
    due_date: date | None = None
    priority: str = "medium"
    rationale: str | None = None


class RecapDecision(BaseModel):
    """A single decision extracted by AI from meeting notes."""

    text: str


class RecapResult(BaseModel):
    """Complete AI recap of meeting notes."""

    summary: str = ""
    decisions: list[RecapDecision] = []
    action_items: list[RecapActionItem] = []
    open_questions: list[str] = []
