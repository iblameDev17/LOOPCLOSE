"""
All enumerations for the LoopClose domain.

Keeping every enum in one file avoids circular imports and makes it easy to
find all possible values when reading or writing code or migration scripts.
All enums are stored as plain strings in the database (native_enum=False).
"""

from __future__ import annotations

from enum import StrEnum

# ── Meeting ───────────────────────────────────────────────────────────────────


class MeetingKind(StrEnum):
    """Whether the record represents a regular meeting or a work handover."""

    meeting = "meeting"
    handover = "handover"


class MeetingStatus(StrEnum):
    """Lifecycle states of a meeting or handover.
    Valid transitions: planned→held→closed, planned|held→cancelled.
    """

    planned = "planned"
    held = "held"
    closed = "closed"
    cancelled = "cancelled"


class Attendance(StrEnum):
    """Per-participant attendance status."""

    invited = "invited"
    attended = "attended"
    absent = "absent"
    no_response = "no_response"
    declined = "declined"


# ── Action items ──────────────────────────────────────────────────────────────


class ActionStatus(StrEnum):
    """Lifecycle states of an action item.
    Terminal states: done, dropped (reached only via close-with-outcome).
    """

    open = "open"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    dropped = "dropped"


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class OutcomeType(StrEnum):
    """How a closed action item was resolved."""

    completed = "completed"
    partially_completed = "partially_completed"
    dropped = "dropped"
    superseded = "superseded"


class EventType(StrEnum):
    """All possible action-item history event types (append-only log)."""

    created = "created"
    updated = "updated"
    reassigned = "reassigned"
    status_changed = "status_changed"
    due_date_changed = "due_date_changed"
    carried_forward = "carried_forward"
    blocked = "blocked"
    closed = "closed"
    reopened = "reopened"
    outcome_recorded = "outcome_recorded"
    kb_linked = "kb_linked"
    nudged = "nudged"


class ItemSource(StrEnum):
    """How an action item or decision was created."""

    manual = "manual"
    ai = "ai"
    heuristic = "heuristic"


# ── AI / status ───────────────────────────────────────────────────────────────


class AiStatus(StrEnum):
    """Tracks the result of the last AI operation on an entity."""

    none = "none"
    ok = "ok"
    fallback = "fallback"
    failed = "failed"


class GeneratedBy(StrEnum):
    ai = "ai"
    fallback = "fallback"


# ── Knowledge base ────────────────────────────────────────────────────────────


class KBSource(StrEnum):
    """Type of knowledge-base document."""

    note = "note"
    document = "document"
    chat = "chat"
    email = "email"
    transcript = "transcript"
    meeting = "meeting"


class IndexStatus(StrEnum):
    """Vector-indexing state of a KB document (Unit 9)."""

    pending = "pending"
    indexed = "indexed"
    failed = "failed"
    not_applicable = "not_applicable"


class EntityType(StrEnum):
    """The type of entity a KB link is attached to."""

    action_item = "action_item"
    decision = "decision"
    meeting = "meeting"


class LinkMethod(StrEnum):
    """How a KB link was created."""

    llm = "llm"
    vector = "vector"
    keyword = "keyword"
    manual = "manual"


# ── Nudge Center ──────────────────────────────────────────────────────────────


class Tone(StrEnum):
    friendly = "friendly"
    firm = "firm"
