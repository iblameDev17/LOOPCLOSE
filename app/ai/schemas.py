"""Pydantic output schemas for AI operations.

These models validate the JSON returned by the LLM before it enters the app.
They are separate from the DB schemas to keep the AI boundary clean.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ── Recap Schemas ─────────────────────────────────────────────────────────────


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


# ── KB Summarize Schemas ──────────────────────────────────────────────────────


class KBSummarizeResult(BaseModel):
    """Summary and tags generated for a knowledge base document."""

    summary: str = ""
    tags: list[str] = []


# ── Link Matching Schemas ─────────────────────────────────────────────────────


class LinkMatch(BaseModel):
    """Single document match from LLM linking."""

    document_id: int
    relevance: float = 1.0
    reason: str = ""


class LinkResult(BaseModel):
    """List of matched documents from LLM linking."""

    matches: list[LinkMatch] = []


# ── Catch-up Brief Schemas ────────────────────────────────────────────────────


class BriefRelatedKnowledge(BaseModel):
    document_id: int
    title: str
    why: str = ""


class BriefResult(BaseModel):
    """Personalized catch-up brief for an attendee, absentee, or handover recipient."""

    tldr: str = ""
    key_decisions: list[str] = []
    your_items: list[str] = []
    changed_since: list[str] = []
    open_questions: list[str] = []
    related_knowledge: list[BriefRelatedKnowledge] = []
    suggested_first_steps: list[str] = []
