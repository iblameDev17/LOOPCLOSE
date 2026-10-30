"""All enumerations for the LoopClose domain.

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

    # Aliases
    MEETING = "meeting"
    HANDOVER = "handover"


class MeetingStatus(StrEnum):
    """Lifecycle states of a meeting or handover.
    Valid transitions: planned→held→closed, planned|held→cancelled.
    """

    planned = "planned"
    held = "held"
    closed = "closed"
    cancelled = "cancelled"

    # Aliases
    PLANNED = "planned"
    HELD = "held"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Attendance(StrEnum):
    """Per-participant attendance status."""

    invited = "invited"
    attended = "attended"
    absent = "absent"
    no_response = "no_response"
    declined = "declined"

    # Aliases
    INVITED = "invited"
    ATTENDED = "attended"
    ABSENT = "absent"
    NO_RESPONSE = "no_response"
    DECLINED = "declined"


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

    # Aliases
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    DROPPED = "dropped"


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"

    # Aliases
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutcomeType(StrEnum):
    """How a closed action item was resolved."""

    completed = "completed"
    partially_completed = "partially_completed"
    dropped = "dropped"
    superseded = "superseded"

    # Aliases
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    DROPPED = "dropped"
    SUPERSEDED = "superseded"


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

    # Aliases
    CREATED = "created"
    UPDATED = "updated"
    REASSIGNED = "reassigned"
    STATUS_CHANGED = "status_changed"
    DUE_DATE_CHANGED = "due_date_changed"
    CARRIED_FORWARD = "carried_forward"
    BLOCKED = "blocked"
    CLOSED = "closed"
    REOPENED = "reopened"
    OUTCOME_RECORDED = "outcome_recorded"
    KB_LINKED = "kb_linked"
    NUDGED = "nudged"


class ItemSource(StrEnum):
    """How an action item or decision was created."""

    manual = "manual"
    ai = "ai"
    heuristic = "heuristic"

    # Aliases
    MANUAL = "manual"
    AI = "ai"
    HEURISTIC = "heuristic"


# ── AI / status ───────────────────────────────────────────────────────────────


class AiStatus(StrEnum):
    """Tracks the result of the last AI operation on an entity."""

    none = "none"
    ok = "ok"
    fallback = "fallback"
    failed = "failed"

    # Aliases
    NONE = "none"
    OK = "ok"
    FALLBACK = "fallback"
    FAILED = "failed"


class GeneratedBy(StrEnum):
    ai = "ai"
    fallback = "fallback"

    # Aliases
    AI = "ai"
    FALLBACK = "fallback"


# ── Knowledge base ────────────────────────────────────────────────────────────


class KBSource(StrEnum):
    """Type of knowledge-base document."""

    note = "note"
    document = "document"
    chat = "chat"
    email = "email"
    transcript = "transcript"
    meeting = "meeting"

    # Aliases
    NOTE = "note"
    DOCUMENT = "document"
    CHAT = "chat"
    EMAIL = "email"
    TRANSCRIPT = "transcript"
    MEETING = "meeting"


class IndexStatus(StrEnum):
    """Vector-indexing state of a KB document (Unit 9)."""

    pending = "pending"
    indexed = "indexed"
    failed = "failed"
    not_applicable = "not_applicable"

    # Aliases
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class EntityType(StrEnum):
    """The type of entity a KB link is attached to."""

    action_item = "action_item"
    decision = "decision"
    meeting = "meeting"

    # Aliases
    ACTION_ITEM = "action_item"
    DECISION = "decision"
    MEETING = "meeting"


class LinkMethod(StrEnum):
    """How a KB link was created."""

    llm = "llm"
    vector = "vector"
    keyword = "keyword"
    manual = "manual"

    # Aliases
    LLM = "llm"
    VECTOR = "vector"
    KEYWORD = "keyword"
    MANUAL = "manual"


# ── Nudge Center ──────────────────────────────────────────────────────────────


class Tone(StrEnum):
    friendly = "friendly"
    firm = "firm"

    # Aliases
    FRIENDLY = "friendly"
    FIRM = "firm"
