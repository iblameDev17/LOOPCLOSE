"""Unit 4 tests — Action items, history, carry-forward, and audit events."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.enums import ActionStatus, EventType, MeetingKind, OutcomeType, Priority
from app.errors import InvalidTransitionError, ValidationFailed
from app.schemas.action_item import ActionItemClose, ActionItemCreate
from app.schemas.meeting import MeetingCreate
from app.schemas.person import PersonCreate
from app.services import (
    action_item_service,
    carry_forward_service,
    meeting_service,
    people_service,
)


def _setup_meeting(db: Session, title: str = "Sprint Planning") -> int:
    person = people_service.create_person(
        db, PersonCreate(name="Dev Lead", email=f"lead_{datetime.now().timestamp()}@example.com")
    )
    meeting = meeting_service.create_meeting(
        db,
        MeetingCreate(
            title=title,
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    return meeting.id


def test_create_action_item_success(db_session: Session):
    m_id = _setup_meeting(db_session)
    owner = people_service.create_person(
        db_session, PersonCreate(name="Alice", email="alice_it@example.com")
    )

    tomorrow = date.today() + timedelta(days=1)
    data = ActionItemCreate(
        title="Deploy auth service to staging",
        description="Run migrations and deploy",
        origin_meeting_id=m_id,
        owner_id=owner.id,
        due_date=tomorrow,
        priority=Priority.HIGH,
    )
    item = action_item_service.create_action_item(db_session, data)

    assert item.id is not None
    assert item.title == "Deploy auth service to staging"
    assert item.origin_meeting_id == m_id
    assert item.current_meeting_id == m_id
    assert item.owner_id == owner.id
    assert item.status == ActionStatus.OPEN.value
    assert item.carried_count == 0
    assert item.is_open is True
    assert item.is_overdue is False

    # Verify append-only created event
    assert len(item.events) == 1
    ev = item.events[0]
    assert ev.event_type == EventType.CREATED.value
    assert ev.actor == "user"
    assert ev.to_value == item.title


def test_create_action_item_due_date_in_past_rejected(db_session: Session):
    m_id = _setup_meeting(db_session)
    yesterday = date.today() - timedelta(days=1)

    with pytest.raises(ValidationFailed) as exc_info:
        data = ActionItemCreate.model_construct(
            title="Old Task",
            origin_meeting_id=m_id,
            due_date=yesterday,
            priority=Priority.MEDIUM,
        )
        action_item_service.create_action_item(db_session, data)

    assert "past" in str(exc_info.value).lower()


def test_create_action_item_title_too_short(db_session: Session):
    m_id = _setup_meeting(db_session)
    with pytest.raises(ValueError):
        ActionItemCreate(
            title="ab",
            origin_meeting_id=m_id,
        )


def test_status_transition_open_to_in_progress(db_session: Session):
    m_id = _setup_meeting(db_session)
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Test item progress", origin_meeting_id=m_id),
    )

    updated = action_item_service.change_status(db_session, item.id, ActionStatus.IN_PROGRESS)
    assert updated.status == ActionStatus.IN_PROGRESS.value

    # Verify event
    assert len(updated.events) == 2
    ev = updated.events[-1]
    assert ev.event_type == EventType.STATUS_CHANGED.value
    assert ev.from_value == ActionStatus.OPEN.value
    assert ev.to_value == ActionStatus.IN_PROGRESS.value


def test_status_transition_blocked_requires_reason(db_session: Session):
    m_id = _setup_meeting(db_session)
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Test item blocking", origin_meeting_id=m_id),
    )

    # Missing reason fails
    with pytest.raises(ValidationFailed) as exc_info:
        action_item_service.change_status(
            db_session, item.id, ActionStatus.BLOCKED, blocked_reason=""
        )
    assert "blocking" in str(exc_info.value).lower()

    # With reason succeeds
    updated = action_item_service.change_status(
        db_session, item.id, ActionStatus.BLOCKED, blocked_reason="Waiting on cloud credentials"
    )
    assert updated.status == ActionStatus.BLOCKED.value
    assert updated.blocked_reason == "Waiting on cloud credentials"

    ev = updated.events[-1]
    assert ev.event_type == EventType.BLOCKED.value
    assert ev.note == "Waiting on cloud credentials"


def test_status_transition_invalid_direct_done(db_session: Session):
    m_id = _setup_meeting(db_session)
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Test item direct done", origin_meeting_id=m_id),
    )

    # Cannot jump to done via status transition without outcome
    with pytest.raises(InvalidTransitionError):
        action_item_service.change_status(db_session, item.id, ActionStatus.DONE)


def test_close_action_item_outcome_and_reopen(db_session: Session):
    m_id = _setup_meeting(db_session)
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Database schema review", origin_meeting_id=m_id),
    )

    # Note too short (< 5 chars) fails
    with pytest.raises(ValueError):
        ActionItemClose(outcome_type=OutcomeType.COMPLETED, outcome_note="Done")

    # Valid close with outcome
    close_data = ActionItemClose(
        outcome_type=OutcomeType.COMPLETED,
        outcome_note="All migration scripts reviewed and approved.",
    )
    closed = action_item_service.close_action_item(db_session, item.id, close_data)

    assert closed.status == ActionStatus.DONE.value
    assert closed.outcome_type == OutcomeType.COMPLETED.value
    assert closed.closed_at is not None
    assert closed.is_open is False

    # Event recorded
    close_ev = closed.events[-1]
    assert close_ev.event_type == EventType.CLOSED.value
    assert "completed" in close_ev.note.lower()

    # Reopening clears outcome and restores open status
    reopened = action_item_service.reopen_action_item(db_session, item.id)
    assert reopened.status == ActionStatus.OPEN.value
    assert reopened.outcome_type is None
    assert reopened.closed_at is None
    assert reopened.is_open is True

    # Reopen event preserves previous outcome in note
    reopen_ev = reopened.events[-1]
    assert reopen_ev.event_type == EventType.REOPENED.value
    assert "completed" in reopen_ev.note.lower()


def test_reassign_action_item_records_event(db_session: Session):
    m_id = _setup_meeting(db_session)
    p1 = people_service.create_person(
        db_session, PersonCreate(name="Original Dev", email="p1@example.com")
    )
    p2 = people_service.create_person(
        db_session, PersonCreate(name="New Dev", email="p2@example.com")
    )

    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Reassign me", origin_meeting_id=m_id, owner_id=p1.id),
    )

    reassigned = action_item_service.reassign_action_item(db_session, item.id, p2.id)
    assert reassigned.owner_id == p2.id

    ev = reassigned.events[-1]
    assert ev.event_type == EventType.REASSIGNED.value
    assert ev.from_value == "Original Dev"
    assert ev.to_value == "New Dev"


def test_carry_forward_semantics(db_session: Session):
    m1_id = _setup_meeting(db_session, title="Sprint Planning 1")
    m2_id = _setup_meeting(db_session, title="Sprint Planning 2")

    # 2 open items and 1 closed item in meeting 1
    it1 = action_item_service.create_action_item(
        db_session, ActionItemCreate(title="Open Item 1", origin_meeting_id=m1_id)
    )
    it2 = action_item_service.create_action_item(
        db_session, ActionItemCreate(title="Open Item 2", origin_meeting_id=m1_id)
    )
    it3 = action_item_service.create_action_item(
        db_session, ActionItemCreate(title="Closed Item 3", origin_meeting_id=m1_id)
    )
    action_item_service.close_action_item(
        db_session,
        it3.id,
        ActionItemClose(outcome_type=OutcomeType.COMPLETED, outcome_note="Completed in meeting 1"),
    )

    # Perform carry-forward
    carried_count = carry_forward_service.carry_forward_items(db_session, m1_id, m2_id)
    assert carried_count == 2

    # Refresh items
    db_session.refresh(it1)
    db_session.refresh(it2)
    db_session.refresh(it3)

    # Open items were moved to current_meeting_id = m2
    assert it1.current_meeting_id == m2_id
    assert it1.origin_meeting_id == m1_id  # Origin never changes!
    assert it1.carried_count == 1

    assert it2.current_meeting_id == m2_id
    assert it2.origin_meeting_id == m1_id
    assert it2.carried_count == 1

    # Closed item was NOT moved
    assert it3.current_meeting_id == m1_id
    assert it3.carried_count == 0

    # Events recorded
    ev1 = it1.events[-1]
    assert ev1.event_type == EventType.CARRIED_FORWARD.value
    assert ev1.from_value == str(m1_id)
    assert ev1.to_value == str(m2_id)


def test_handover_bulk_reassign(db_session: Session):
    p_from = people_service.create_person(
        db_session, PersonCreate(name="Outgoing Lead", email="from@example.com")
    )
    p_to = people_service.create_person(
        db_session, PersonCreate(name="Incoming Lead", email="to@example.com")
    )

    handover = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Handover Sync",
            kind=MeetingKind.HANDOVER,
            scheduled_at=datetime.now(UTC),
            handover_from_id=p_from.id,
            handover_to_id=p_to.id,
            participant_ids=[p_from.id, p_to.id],
        ),
    )

    # Create 3 open items for outgoing lead
    for i in range(3):
        action_item_service.create_action_item(
            db_session,
            ActionItemCreate(
                title=f"Handover item {i}",
                origin_meeting_id=handover.id,
                owner_id=p_from.id,
            ),
        )

    count = meeting_service.reassign_handover_items(db_session, handover.id)
    assert count == 3

    # All items now owned by p_to
    reassigned_items = action_item_service.list_action_items(db_session, owner_id=p_to.id)
    assert len(reassigned_items) == 3


def test_overdue_computed_property(db_session: Session):
    m_id = _setup_meeting(db_session)
    yesterday = date.today() - timedelta(days=2)
    tomorrow = date.today() + timedelta(days=2)

    # We use model_construct to create an item with yesterday due date (simulating aging)
    item_overdue = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(title="Fresh item", origin_meeting_id=m_id, due_date=tomorrow),
    )
    # Manually backdate due_date in database
    item_overdue.due_date = yesterday
    db_session.commit()
    db_session.refresh(item_overdue)

    assert item_overdue.is_overdue is True
    assert item_overdue.overdue_days == 2

    # Closing it removes overdue status
    action_item_service.close_action_item(
        db_session,
        item_overdue.id,
        ActionItemClose(outcome_type=OutcomeType.COMPLETED, outcome_note="Done late"),
    )
    assert item_overdue.is_overdue is False


def test_web_items_routes(client):
    # Test GET /items
    resp = client.get("/items")
    assert resp.status_code == 200
    assert "Action Items" in resp.text

    # Test GET /dashboard contains wired cards
    dash = client.get("/")
    assert dash.status_code == 200
    assert "Needs attention" in dash.text
    assert "Upcoming meetings" in dash.text
