"""Unit 3 tests — Core domain: people, meetings & handovers.

Covers:
- Person creation, listing, duplicate email validation
- Meeting creation (regular meeting + handover)
- Handover validation (from != to, active people required)
- Meeting lifecycle state machine (valid transitions & invalid transitions)
- Participants & attendance updates
- Decision CRUD
- Notes saving and length cap
- Viewing as cookie endpoint
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.enums import Attendance, MeetingKind, MeetingStatus
from app.errors import InvalidTransitionError, ValidationFailed
from app.schemas.meeting import MeetingCreate
from app.schemas.person import PersonCreate
from app.services import meeting_service, people_service

# ── People tests ─────────────────────────────────────────────────────────────


def test_create_person_success(db_session: Session):
    p = people_service.create_person(
        db_session,
        PersonCreate(name="Priya Sharma", email="priya@example.com", role_title="Lead"),
    )
    assert p.id is not None
    assert p.name == "Priya Sharma"
    assert p.email == "priya@example.com"
    assert p.initials == "PS"
    assert p.is_active is True


def test_create_person_duplicate_email_fails(db_session: Session):
    people_service.create_person(
        db_session,
        PersonCreate(name="User One", email="same@example.com"),
    )
    with pytest.raises(ValidationFailed) as exc_info:
        people_service.create_person(
            db_session,
            PersonCreate(name="User Two", email="same@example.com"),
        )
    assert "already used" in exc_info.value.message


# ── Meeting creation & handover tests ─────────────────────────────────────────


def test_create_regular_meeting_success(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Alice Tech", email="alice@example.com")
    )
    sched = datetime.now(UTC) + timedelta(days=1)
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Sprint Planning",
            kind=MeetingKind.MEETING,
            scheduled_at=sched,
            participant_ids=[p.id],
        ),
    )
    assert m.id is not None
    assert m.title == "Sprint Planning"
    assert m.status == MeetingStatus.PLANNED.value
    assert len(m.participants) == 1
    assert m.participants[0].person_id == p.id
    assert m.participants[0].attendance == Attendance.INVITED.value


def test_create_handover_success(db_session: Session):
    p1 = people_service.create_person(
        db_session, PersonCreate(name="Sender Dev", email="sender@example.com")
    )
    p2 = people_service.create_person(
        db_session, PersonCreate(name="Receiver Dev", email="receiver@example.com")
    )
    sched = datetime.now(UTC) + timedelta(days=2)
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Project Handover",
            kind=MeetingKind.HANDOVER,
            scheduled_at=sched,
            handover_from_id=p1.id,
            handover_to_id=p2.id,
        ),
    )
    assert m.id is not None
    assert m.is_handover is True
    assert m.handover_from_id == p1.id
    assert m.handover_to_id == p2.id
    # Both from and to are auto-added as participants
    p_ids = {part.person_id for part in m.participants}
    assert p1.id in p_ids
    assert p2.id in p_ids


def test_handover_same_person_rejected(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Solo Dev", email="solo@example.com")
    )
    sched = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(ValidationFailed) as exc_info:
        meeting_service.create_meeting(
            db_session,
            MeetingCreate.model_construct(
                title="Self Handover",
                kind=MeetingKind.HANDOVER,
                scheduled_at=sched,
                handover_from_id=p.id,
                handover_to_id=p.id,
                participant_ids=[],
            ),
        )
    assert "two different people" in exc_info.value.message


# ── Meeting lifecycle state machine tests ─────────────────────────────────────


def test_lifecycle_planned_to_held_to_closed(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Tester", email="tester@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Lifecycle Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )
    assert m.status == MeetingStatus.PLANNED.value

    # planned -> held
    m = meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.HELD)
    assert m.status == MeetingStatus.HELD.value

    # held -> closed
    m = meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.CLOSED)
    assert m.status == MeetingStatus.CLOSED.value
    assert m.closed_at is not None
    assert m.is_closed is True


def test_lifecycle_planned_to_cancelled(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Tester 2", email="tester2@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Cancel Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )
    m = meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.CANCELLED)
    assert m.status == MeetingStatus.CANCELLED.value
    assert m.is_closed is True


def test_lifecycle_invalid_transitions_raise_error(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Tester 3", email="tester3@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Invalid Transition Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )

    # planned -> closed directly is rejected
    with pytest.raises(InvalidTransitionError) as exc_info:
        meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.CLOSED)
    assert "must be marked as held before closing" in exc_info.value.message

    # Move to held then closed
    meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.HELD)
    meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.CLOSED)

    # closed -> reopened is rejected
    with pytest.raises(InvalidTransitionError) as exc_info:
        meeting_service.update_meeting_status(db_session, m.id, MeetingStatus.PLANNED)
    assert "A closed meeting can't be reopened" in exc_info.value.message


# ── Attendance & Decisions tests ──────────────────────────────────────────────


def test_participant_attendance_update(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Attendee", email="attendee@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Attendance Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )
    part = meeting_service.update_participant_attendance(
        db_session, m.id, p.id, Attendance.ATTENDED
    )
    assert part.attendance == Attendance.ATTENDED.value


def test_decision_crud(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Decider", email="decider@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Decisions Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )
    dec = meeting_service.add_decision(db_session, m.id, "Adopt PostgreSQL for prod.")
    assert dec.id is not None
    assert dec.text == "Adopt PostgreSQL for prod."

    meeting_service.delete_decision(db_session, dec.id)
    refreshed = meeting_service.get_meeting(db_session, m.id)
    assert len(refreshed.decisions) == 0


def test_save_notes_and_cap(db_session: Session):
    p = people_service.create_person(
        db_session, PersonCreate(name="Note Taker", email="notes@example.com")
    )
    m = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Notes Test",
            scheduled_at=datetime.now(UTC),
            participant_ids=[p.id],
        ),
    )
    m = meeting_service.save_notes(db_session, m.id, "Discussion about architecture.")
    assert m.raw_notes == "Discussion about architecture."

    # Cap at 50,000 characters
    with pytest.raises(ValidationFailed):
        meeting_service.save_notes(db_session, m.id, "x" * 50001)


# ── HTTP Router Tests ─────────────────────────────────────────────────────────


def test_people_page_returns_200(client):
    response = client.get("/people")
    assert response.status_code == 200
    assert b"Team Members" in response.content


def test_meetings_list_page_returns_200(client):
    response = client.get("/meetings")
    assert response.status_code == 200
    assert b"Meetings & Handovers" in response.content


def test_new_meeting_page_returns_200(client):
    response = client.get("/meetings/new")
    assert response.status_code == 200
    assert b"New Meeting or Handover" in response.content


def test_viewing_as_cookie_sets_header(client):
    response = client.post("/viewing-as", data={"person_id": "1"}, follow_redirects=False)
    assert "loopclose_view_as=1" in response.headers.get("set-cookie", "")
