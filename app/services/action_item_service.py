"""Action item service implementing full lifecycle, transitions, events, and audit logging."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.enums import ActionStatus, EventType, ItemSource, OutcomeType, Priority
from app.errors import InvalidTransitionError, NotFoundError, ValidationFailed
from app.logging_config import log_event, request_id_var
from app.models.action_item import ActionItem, ActionItemEvent
from app.models.meeting import Meeting
from app.models.person import Person
from app.schemas.action_item import (
    ActionItemClose,
    ActionItemCreate,
    ActionItemUpdate,
)

logger = logging.getLogger("app.items")

_OPEN_STATUSES = frozenset(
    {
        ActionStatus.OPEN.value,
        ActionStatus.IN_PROGRESS.value,
        ActionStatus.BLOCKED.value,
        "open",
        "in_progress",
        "blocked",
    }
)
_CLOSED_STATUSES = frozenset(
    {
        ActionStatus.DONE.value,
        ActionStatus.DROPPED.value,
        "done",
        "dropped",
    }
)


def _get_request_id() -> str:
    return request_id_var.get("-")


def create_action_item(
    db: Session,
    data: ActionItemCreate,
    actor: str = "user",
) -> ActionItem:
    """Create an action item with validation, created event, and audit log."""
    # Validate origin meeting
    meeting = db.get(Meeting, data.origin_meeting_id)
    if not meeting:
        raise NotFoundError("Meeting", data.origin_meeting_id)

    # Validate owner if assigned
    if data.owner_id is not None:
        owner = db.get(Person, data.owner_id)
        if not owner:
            raise NotFoundError("Person", data.owner_id)
        if not owner.is_active:
            raise ValidationFailed("Choose an active person as owner.", field="owner_id")

    # Validate due date not in past
    if data.due_date is not None and data.due_date < date.today():
        raise ValidationFailed("Due date can't be in the past.", field="due_date")

    curr_meeting_id = (
        data.current_meeting_id if data.current_meeting_id is not None else data.origin_meeting_id
    )

    item = ActionItem(
        title=data.title,
        description=data.description,
        origin_meeting_id=data.origin_meeting_id,
        current_meeting_id=curr_meeting_id,
        owner_id=data.owner_id,
        due_date=data.due_date,
        priority=(
            data.priority.value if isinstance(data.priority, Priority) else str(data.priority)
        ),
        status=ActionStatus.OPEN.value,
        source=data.source.value if isinstance(data.source, ItemSource) else str(data.source),
        carried_count=0,
    )
    db.add(item)
    db.flush()

    # Append append-only created event
    event = ActionItemEvent(
        action_item_id=item.id,
        event_type=EventType.CREATED.value,
        actor=actor,
        to_value=item.title,
        meeting_id=item.origin_meeting_id,
        request_id=_get_request_id(),
    )
    db.add(event)
    db.commit()
    db.refresh(item)

    log_event(
        logger,
        "item.created",
        item_id=item.id,
        origin_meeting_id=item.origin_meeting_id,
        owner_id=item.owner_id,
        priority=item.priority,
        source=item.source,
    )
    return item


def get_action_item(db: Session, item_id: int) -> ActionItem:
    """Retrieve an action item with full relationships loaded, or raise 404."""
    stmt = (
        select(ActionItem)
        .options(
            joinedload(ActionItem.owner),
            joinedload(ActionItem.origin_meeting),
            joinedload(ActionItem.current_meeting),
            joinedload(ActionItem.events),
        )
        .where(ActionItem.id == item_id)
    )
    item = db.execute(stmt).unique().scalar_one_or_none()
    if not item:
        raise NotFoundError("ActionItem", item_id)
    return item


def list_action_items(
    db: Session,
    status: str | None = None,
    owner_id: int | None = None,
    meeting_id: int | None = None,
    is_overdue: bool | None = None,
    sort_by: str = "due_date",
) -> list[ActionItem]:
    """List and filter action items."""
    stmt = select(ActionItem).options(
        joinedload(ActionItem.owner),
        joinedload(ActionItem.current_meeting),
        joinedload(ActionItem.origin_meeting),
    )

    if status:
        stmt = stmt.where(ActionItem.status == status)

    if owner_id:
        stmt = stmt.where(ActionItem.owner_id == owner_id)

    if meeting_id:
        stmt = stmt.where(
            (ActionItem.current_meeting_id == meeting_id)
            | (ActionItem.origin_meeting_id == meeting_id)
        )

    if is_overdue is True:
        stmt = stmt.where(
            ActionItem.due_date < date.today(),
            ActionItem.status.in_(_OPEN_STATUSES),
        )

    if sort_by == "due_date":
        # Put null due dates last
        stmt = stmt.order_by(ActionItem.due_date.asc().nulls_last(), ActionItem.id.desc())
    else:
        stmt = stmt.order_by(ActionItem.created_at.desc())

    return list(db.execute(stmt).scalars().all())


def update_action_item(
    db: Session,
    item_id: int,
    data: ActionItemUpdate,
    actor: str = "user",
) -> ActionItem:
    """Update title, description, owner, due date, or priority."""
    item = get_action_item(db, item_id)

    # Owner update
    if data.owner_id is not None and data.owner_id != item.owner_id:
        reassign_action_item(db, item_id, data.owner_id, actor=actor)
        db.refresh(item)

    # Due date update
    if data.due_date is not None and data.due_date != item.due_date:
        old_due = str(item.due_date) if item.due_date else "none"
        new_due = str(data.due_date)
        item.due_date = data.due_date
        db.add(
            ActionItemEvent(
                action_item_id=item.id,
                event_type=EventType.DUE_DATE_CHANGED.value,
                actor=actor,
                from_value=old_due,
                to_value=new_due,
                meeting_id=item.current_meeting_id,
                request_id=_get_request_id(),
            )
        )
        log_event(
            logger,
            "item.due_date_changed",
            item_id=item.id,
            from_due=old_due,
            to_due=new_due,
        )

    # Title & description
    if data.title and data.title != item.title:
        old_title = item.title
        item.title = data.title
        db.add(
            ActionItemEvent(
                action_item_id=item.id,
                event_type=EventType.UPDATED.value,
                actor=actor,
                from_value=old_title,
                to_value=item.title,
                meeting_id=item.current_meeting_id,
                request_id=_get_request_id(),
            )
        )

    if data.description is not None:
        item.description = data.description

    if data.priority is not None:
        p_val = data.priority.value if isinstance(data.priority, Priority) else str(data.priority)
        item.priority = p_val

    db.commit()
    db.refresh(item)
    return item


def change_status(
    db: Session,
    item_id: int,
    new_status: ActionStatus | str,
    blocked_reason: str | None = None,
    actor: str = "user",
) -> ActionItem:
    """Transition between open, in_progress, and blocked states."""
    item = get_action_item(db, item_id)
    status_str = new_status.value if isinstance(new_status, ActionStatus) else str(new_status)

    if status_str in _CLOSED_STATUSES:
        raise InvalidTransitionError("Use close with outcome to mark an item done or dropped.")

    if item.status in _CLOSED_STATUSES:
        raise InvalidTransitionError("Item is closed. Use reopen first.")

    if status_str == ActionStatus.BLOCKED.value or status_str == "blocked":
        if not blocked_reason or len(blocked_reason.strip()) < 3:
            raise ValidationFailed("Say what is blocking this.", field="blocked_reason")
        item.blocked_reason = blocked_reason.strip()
    else:
        item.blocked_reason = None

    old_status = item.status
    item.status = status_str

    event_type = (
        EventType.BLOCKED.value
        if status_str in (ActionStatus.BLOCKED.value, "blocked")
        else EventType.STATUS_CHANGED.value
    )
    db.add(
        ActionItemEvent(
            action_item_id=item.id,
            event_type=event_type,
            actor=actor,
            from_value=old_status,
            to_value=status_str,
            note=item.blocked_reason,
            meeting_id=item.current_meeting_id,
            request_id=_get_request_id(),
        )
    )
    db.commit()
    db.refresh(item)

    log_event(
        logger,
        "item.status_changed",
        item_id=item.id,
        from_status=old_status,
        to_status=status_str,
    )
    if status_str in (ActionStatus.BLOCKED.value, "blocked"):
        log_event(logger, "item.blocked", item_id=item.id)

    return item


def reassign_action_item(
    db: Session,
    item_id: int,
    new_owner_id: int | None,
    actor: str = "user",
) -> ActionItem:
    """Reassign owner of an action item and record reassigned event."""
    item = get_action_item(db, item_id)
    old_owner_name = item.owner.name if item.owner else "Unassigned"
    new_owner_name = "Unassigned"

    if new_owner_id is not None:
        new_owner = db.get(Person, new_owner_id)
        if not new_owner:
            raise NotFoundError("Person", new_owner_id)
        if not new_owner.is_active:
            raise ValidationFailed("Choose an active person as owner.", field="owner_id")
        new_owner_name = new_owner.name

    old_owner_id = item.owner_id
    item.owner_id = new_owner_id

    db.add(
        ActionItemEvent(
            action_item_id=item.id,
            event_type=EventType.REASSIGNED.value,
            actor=actor,
            from_value=old_owner_name,
            to_value=new_owner_name,
            meeting_id=item.current_meeting_id,
            request_id=_get_request_id(),
        )
    )
    db.commit()
    db.refresh(item)

    log_event(
        logger,
        "item.reassigned",
        item_id=item.id,
        from_owner_id=old_owner_id,
        to_owner_id=new_owner_id,
    )
    return item


def close_action_item(
    db: Session,
    item_id: int,
    data: ActionItemClose,
    actor: str = "user",
) -> ActionItem:
    """Close an item with outcome recording (only way to reach done/dropped)."""
    item = get_action_item(db, item_id)

    ot_str = (
        data.outcome_type.value
        if isinstance(data.outcome_type, OutcomeType)
        else str(data.outcome_type)
    )
    note_str = data.outcome_note.strip()
    if len(note_str) < 5:
        raise ValidationFailed("Record the outcome before closing.", field="outcome_note")

    # outcome_type -> status mapping per PRD §8.2
    if ot_str in ("completed", "partially_completed"):
        final_status = ActionStatus.DONE.value
    elif ot_str in ("dropped", "superseded"):
        final_status = ActionStatus.DROPPED.value
    else:
        raise ValidationFailed(f"Invalid outcome type: {ot_str}", field="outcome_type")

    old_status = item.status
    item.status = final_status
    item.outcome_type = ot_str
    item.outcome_note = note_str
    item.closed_at = datetime.now(UTC)

    db.add(
        ActionItemEvent(
            action_item_id=item.id,
            event_type=EventType.CLOSED.value,
            actor=actor,
            from_value=old_status,
            to_value=final_status,
            note=f"{ot_str}: {note_str}",
            meeting_id=item.current_meeting_id,
            request_id=_get_request_id(),
        )
    )
    db.commit()
    db.refresh(item)

    log_event(
        logger,
        "item.closed",
        item_id=item.id,
        outcome_type=ot_str,
        status=final_status,
    )
    return item


def reopen_action_item(
    db: Session,
    item_id: int,
    actor: str = "user",
) -> ActionItem:
    """Reopen a closed item back to open status while preserving outcome in history event."""
    item = get_action_item(db, item_id)
    if item.status not in _CLOSED_STATUSES:
        raise InvalidTransitionError("Item is already open.")

    old_status = item.status
    prev_outcome_summary = f"Previous outcome: {item.outcome_type} — {item.outcome_note}"

    item.status = ActionStatus.OPEN.value
    item.outcome_type = None
    item.outcome_note = None
    item.closed_at = None
    item.blocked_reason = None

    db.add(
        ActionItemEvent(
            action_item_id=item.id,
            event_type=EventType.REOPENED.value,
            actor=actor,
            from_value=old_status,
            to_value=ActionStatus.OPEN.value,
            note=prev_outcome_summary,
            meeting_id=item.current_meeting_id,
            request_id=_get_request_id(),
        )
    )
    db.commit()
    db.refresh(item)

    log_event(logger, "item.reopened", item_id=item.id)
    return item
