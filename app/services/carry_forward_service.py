"""Carry-forward service for transferring open action items across meetings."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.enums import ActionStatus, EventType
from app.errors import NotFoundError
from app.logging_config import log_event, request_id_var
from app.models.action_item import ActionItem, ActionItemEvent
from app.models.meeting import Meeting

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


def _get_request_id() -> str:
    return request_id_var.get("-")


def carry_forward_items(
    db: Session,
    source_meeting_id: int,
    target_meeting_id: int,
    item_ids: list[int] | None = None,
    actor: str = "user",
) -> int:
    """Carry forward open items from source meeting to target meeting."""
    source_meeting = db.get(Meeting, source_meeting_id)
    if not source_meeting:
        raise NotFoundError("Meeting", source_meeting_id)

    target_meeting = db.get(Meeting, target_meeting_id)
    if not target_meeting:
        raise NotFoundError("Meeting", target_meeting_id)

    stmt = select(ActionItem).where(
        ActionItem.current_meeting_id == source_meeting_id,
        ActionItem.status.in_(_OPEN_STATUSES),
    )
    if item_ids:
        stmt = stmt.where(ActionItem.id.in_(item_ids))

    items = list(db.execute(stmt).scalars().all())
    if not items:
        return 0

    count = 0
    for item in items:
        old_meeting_id = item.current_meeting_id
        item.current_meeting_id = target_meeting_id
        item.carried_count += 1

        db.add(
            ActionItemEvent(
                action_item_id=item.id,
                event_type=EventType.CARRIED_FORWARD.value,
                actor=actor,
                from_value=str(old_meeting_id),
                to_value=str(target_meeting_id),
                meeting_id=target_meeting_id,
                note=f"Carried forward from meeting #{old_meeting_id}",
                request_id=_get_request_id(),
            )
        )
        count += 1
        log_event(
            logger,
            "item.carried_forward",
            item_id=item.id,
            from_meeting_id=old_meeting_id,
            to_meeting_id=target_meeting_id,
            carried_count=item.carried_count,
        )

    db.commit()

    log_event(
        logger,
        "meeting.carry_forward",
        source_meeting_id=source_meeting_id,
        target_meeting_id=target_meeting_id,
        count=count,
    )
    return count


def get_carried_items(db: Session, meeting_id: int) -> list[ActionItem]:
    """Retrieve items that were carried into this meeting from a previous meeting."""
    stmt = (
        select(ActionItem)
        .options(
            joinedload(ActionItem.owner),
            joinedload(ActionItem.origin_meeting),
        )
        .where(
            ActionItem.current_meeting_id == meeting_id,
            ActionItem.origin_meeting_id != meeting_id,
        )
        .order_by(ActionItem.carried_count.desc(), ActionItem.due_date.asc().nulls_last())
    )
    return list(db.execute(stmt).scalars().all())
