"""Meeting service: manages meeting/handover creation, lifecycle, participants, and decisions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import Attendance, ItemSource, MeetingKind, MeetingStatus
from app.errors import InvalidTransitionError, NotFoundError, ValidationFailed
from app.logging_config import log_event
from app.models.decision import Decision
from app.models.meeting import Meeting, MeetingParticipant
from app.models.person import Person
from app.schemas.meeting import MeetingCreate, MeetingUpdate

logger = logging.getLogger("app.meetings")

VALID_TRANSITIONS: dict[str, set[str]] = {
    MeetingStatus.PLANNED.value: {MeetingStatus.HELD.value, MeetingStatus.CANCELLED.value},
    MeetingStatus.HELD.value: {MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value},
    MeetingStatus.CLOSED.value: set(),
    MeetingStatus.CANCELLED.value: set(),
}


def list_meetings(
    db: Session,
    kind: str | None = None,
    status: str | None = None,
) -> list[Meeting]:
    """List meetings with optional filtering by kind and status."""
    stmt = (
        select(Meeting)
        .options(
            selectinload(Meeting.participants).selectinload(MeetingParticipant.person),
            selectinload(Meeting.handover_from),
            selectinload(Meeting.handover_to),
            selectinload(Meeting.current_items),
        )
        .order_by(Meeting.scheduled_at.desc())
    )

    if kind:
        stmt = stmt.where(Meeting.kind == kind)
    if status:
        stmt = stmt.where(Meeting.status == status)

    return list(db.scalars(stmt).all())


def get_meeting(db: Session, meeting_id: int) -> Meeting:
    """Retrieve a meeting by ID with all relations eagerly loaded."""
    stmt = (
        select(Meeting)
        .options(
            selectinload(Meeting.participants).selectinload(MeetingParticipant.person),
            selectinload(Meeting.decisions),
            selectinload(Meeting.handover_from),
            selectinload(Meeting.handover_to),
            selectinload(Meeting.previous_meeting),
            selectinload(Meeting.current_items),
        )
        .where(Meeting.id == meeting_id)
    )
    meeting = db.scalar(stmt)
    if not meeting:
        raise NotFoundError(f"Meeting with id {meeting_id} not found.")
    return meeting


def create_meeting(db: Session, data: MeetingCreate) -> Meeting:
    """Create a new meeting or handover with validated participants and relationships."""
    is_handover = data.kind == MeetingKind.HANDOVER or data.kind == MeetingKind.HANDOVER.value

    if is_handover:
        if not data.handover_from_id or not data.handover_to_id:
            raise ValidationFailed("Choose both people for the handover.", field="handover_from_id")
        if data.handover_from_id == data.handover_to_id:
            raise ValidationFailed("Choose two different people.", field="handover_to_id")

        from_person = db.get(Person, data.handover_from_id)
        to_person = db.get(Person, data.handover_to_id)
        if not from_person or not from_person.is_active:
            raise ValidationFailed(
                "Handover sender must be an active person.", field="handover_from_id"
            )
        if not to_person or not to_person.is_active:
            raise ValidationFailed(
                "Handover recipient must be an active person.", field="handover_to_id"
            )
    else:
        if not data.participant_ids:
            raise ValidationFailed("Add at least one participant.", field="participant_ids")

    if data.previous_meeting_id:
        prev = db.get(Meeting, data.previous_meeting_id)
        if not prev:
            raise ValidationFailed("Previous meeting not found.", field="previous_meeting_id")

    meeting = Meeting(
        kind=data.kind.value if hasattr(data.kind, "value") else str(data.kind),
        title=data.title.strip(),
        scheduled_at=data.scheduled_at,
        agenda=data.agenda.strip() if data.agenda else None,
        previous_meeting_id=data.previous_meeting_id,
        handover_from_id=data.handover_from_id if is_handover else None,
        handover_to_id=data.handover_to_id if is_handover else None,
        status=MeetingStatus.PLANNED.value,
    )
    db.add(meeting)
    db.flush()

    # Collect participants (for handover, auto-add both from and to)
    p_ids = set(data.participant_ids)
    if is_handover:
        p_ids.add(data.handover_from_id)  # type: ignore[arg-type]
        p_ids.add(data.handover_to_id)  # type: ignore[arg-type]

    for pid in p_ids:
        person = db.get(Person, pid)
        if person:
            participant = MeetingParticipant(
                meeting_id=meeting.id,
                person_id=pid,
                attendance=Attendance.INVITED.value,
            )
            db.add(participant)

    db.commit()
    db.refresh(meeting)

    log_event(
        logger,
        "meeting.created",
        meeting_id=meeting.id,
        kind=meeting.kind,
        title=meeting.title,
        participants_count=len(p_ids),
    )
    return get_meeting(db, meeting.id)


def update_meeting(db: Session, meeting_id: int, data: MeetingUpdate) -> Meeting:
    """Update title, scheduled date, or agenda of an active meeting."""
    meeting = get_meeting(db, meeting_id)

    if meeting.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value):
        raise InvalidTransitionError("Closed or cancelled meetings cannot be edited.")

    if data.title is not None:
        meeting.title = data.title.strip()
    if data.scheduled_at is not None:
        meeting.scheduled_at = data.scheduled_at
    if data.agenda is not None:
        meeting.agenda = data.agenda.strip() if data.agenda else None

    meeting.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(meeting)

    log_event(logger, "meeting.updated", meeting_id=meeting.id)
    return meeting


def update_meeting_status(db: Session, meeting_id: int, new_status: str | MeetingStatus) -> Meeting:
    """Transition meeting through lifecycle state machine: planned -> held -> closed / cancelled."""
    meeting = get_meeting(db, meeting_id)
    target = new_status.value if hasattr(new_status, "value") else str(new_status)
    current = meeting.status

    if current == target:
        return meeting

    if current == MeetingStatus.CLOSED.value:
        raise InvalidTransitionError("A closed meeting can't be reopened.")
    if current == MeetingStatus.CANCELLED.value:
        raise InvalidTransitionError("A cancelled meeting cannot change status.")

    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        if current == MeetingStatus.PLANNED.value and target == MeetingStatus.CLOSED.value:
            raise InvalidTransitionError("A planned meeting must be marked as held before closing.")
        raise InvalidTransitionError(f"Cannot transition meeting from {current} to {target}.")

    meeting.status = target
    if target == MeetingStatus.CLOSED.value:
        meeting.closed_at = datetime.now(UTC)
    meeting.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(meeting)

    log_event(
        logger,
        "meeting.status_changed",
        meeting_id=meeting.id,
        from_status=current,
        to_status=target,
    )
    return meeting


def save_notes(db: Session, meeting_id: int, raw_notes: str) -> Meeting:
    """Save raw meeting notes."""
    meeting = get_meeting(db, meeting_id)
    if meeting.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value):
        raise InvalidTransitionError("Notes cannot be edited for closed or cancelled meetings.")

    if len(raw_notes) > 50000:
        raise ValidationFailed("Raw notes cannot exceed 50,000 characters.", field="raw_notes")

    meeting.raw_notes = raw_notes
    meeting.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(meeting)

    log_event(
        logger,
        "meeting.notes_saved",
        meeting_id=meeting.id,
        notes_length=len(raw_notes),
    )
    return meeting


def add_participant(
    db: Session,
    meeting_id: int,
    person_id: int,
    attendance: str | Attendance = Attendance.INVITED,
) -> MeetingParticipant:
    """Add a person as a participant to a meeting."""
    meeting = get_meeting(db, meeting_id)
    if meeting.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value):
        raise InvalidTransitionError("Cannot add participants to a closed or cancelled meeting.")

    person = db.get(Person, person_id)
    if not person:
        raise NotFoundError(f"Person with id {person_id} not found.")

    existing = db.scalar(
        select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.person_id == person_id,
        )
    )
    if existing:
        raise ValidationFailed("Person is already a participant.")

    att_val = attendance.value if hasattr(attendance, "value") else str(attendance)
    participant = MeetingParticipant(
        meeting_id=meeting_id,
        person_id=person_id,
        attendance=att_val,
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    log_event(
        logger,
        "meeting.participant_added",
        meeting_id=meeting_id,
        person_id=person_id,
    )
    return participant


def update_participant_attendance(
    db: Session,
    meeting_id: int,
    person_id: int,
    attendance: str | Attendance,
) -> MeetingParticipant:
    """Update participant attendance record."""
    participant = db.scalar(
        select(MeetingParticipant).where(
            MeetingParticipant.meeting_id == meeting_id,
            MeetingParticipant.person_id == person_id,
        )
    )
    if not participant:
        raise NotFoundError("Participant record not found.")

    att_val = attendance.value if hasattr(attendance, "value") else str(attendance)
    participant.attendance = att_val
    db.commit()
    db.refresh(participant)

    log_event(
        logger,
        "meeting.participant_updated",
        meeting_id=meeting_id,
        person_id=person_id,
        attendance=att_val,
    )
    return participant


def add_decision(
    db: Session,
    meeting_id: int,
    text: str,
    source: str | ItemSource = ItemSource.MANUAL,
) -> Decision:
    """Add a key decision to the meeting."""
    meeting = get_meeting(db, meeting_id)
    if meeting.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value):
        raise InvalidTransitionError("Cannot add decisions to a closed or cancelled meeting.")

    clean_text = text.strip()
    if len(clean_text) < 3:
        raise ValidationFailed("Decision text must be at least 3 characters.", field="text")
    if len(clean_text) > 1000:
        raise ValidationFailed("Decision text cannot exceed 1000 characters.", field="text")

    src_val = source.value if hasattr(source, "value") else str(source)
    decision = Decision(meeting_id=meeting_id, text=clean_text, source=src_val)
    db.add(decision)
    db.commit()
    db.refresh(decision)

    log_event(
        logger,
        "meeting.decision_added",
        meeting_id=meeting_id,
        decision_id=decision.id,
    )
    return decision


def delete_decision(db: Session, decision_id: int) -> None:
    """Delete a key decision."""
    decision = db.get(Decision, decision_id)
    if not decision:
        raise NotFoundError(f"Decision with id {decision_id} not found.")

    meeting = db.get(Meeting, decision.meeting_id)
    if meeting and meeting.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value):
        raise InvalidTransitionError("Cannot delete decisions from a closed or cancelled meeting.")

    mid = decision.meeting_id
    db.delete(decision)
    db.commit()

    log_event(logger, "meeting.decision_deleted", meeting_id=mid, decision_id=decision_id)


def reassign_handover_items_stub(db: Session, meeting_id: int) -> int:
    """Stub for handover item bulk-reassign (completed in Unit 4)."""
    meeting = get_meeting(db, meeting_id)
    if not meeting.is_handover or not meeting.handover_from_id or not meeting.handover_to_id:
        return 0

    log_event(
        logger,
        "meeting.handover_reassign",
        meeting_id=meeting.id,
        count=0,
    )
    return 0
