"""Unit 6 tests — Knowledge Base, Linking, and Catch-up Briefs.

Covers:
- Document creation, validation, and AI summarization.
- Summarizer fallback (content[:200]) when AI fails.
- Document upload validation (reject > 1MB, reject binary non-UTF-8).
- find_related() happy path with FakeProvider and keyword fallback.
- Link creation, unique constraint (uq_kb_link), deletion, and item audit event.
- Auto-index meeting notes to KB on meeting close.
- Catch-up brief default person selection logic.
- Catch-up brief generation (AI happy path and heuristic template fallback).
- Web routes: /kb, /kb/new, /kb/{id}, /kb/{id}/reindex, /links, /links/{id}/delete,
  /meetings/{id}/suggest-links, /items/{id}/suggest-links, /meetings/{id}/brief.

All tests MUST use FakeProvider and run 100% offline without hitting the network (AGENTS.md §6.8).
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.ai.client import get_provider, reset_provider
from app.ai.fake import FakeProvider
from app.enums import Attendance, KBSource, LinkMethod, MeetingKind, Priority
from app.errors import ValidationFailed
from app.kb import retrieval
from app.models.kb import KBDocument, KBLink
from app.schemas.action_item import ActionItemCreate
from app.schemas.meeting import MeetingCreate
from app.schemas.person import PersonCreate
from app.services import (
    action_item_service,
    brief_service,
    kb_service,
    meeting_service,
    people_service,
)


@pytest.fixture(autouse=True)
def setup_fake_provider():
    """Ensure FakeProvider is clean and in non-failing mode for each test."""
    reset_provider()
    provider = get_provider()
    if isinstance(provider, FakeProvider):
        provider.set_fail_mode(None)
        provider.call_count = 0
    yield
    reset_provider()


# ── Document Creation & Summarization ─────────────────────────────────────────


def test_create_document_happy_path(db_session):
    """Creating a document triggers AI summarization."""
    doc = kb_service.create_document(
        db_session,
        title="Architecture Decision Record 1",
        content="This ADR describes our migration from a monolithic app to modular microservices. We chose FastAPI.",
        source_type=KBSource.DOCUMENT,
    )
    assert doc.id is not None
    assert doc.title == "Architecture Decision Record 1"
    assert doc.summary is not None
    assert "deployment architecture" in doc.summary.lower()


def test_create_document_summary_fallback_on_ai_failure(db_session):
    """When the AI summarizer fails, summary falls back to content[:200]."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    provider.set_fail_mode("timeout")

    long_content = "Alpha " * 60  # 360 chars
    doc = kb_service.create_document(
        db_session,
        title="Failing AI Doc",
        content=long_content,
        source_type=KBSource.NOTE,
    )
    assert doc.id is not None
    assert len(doc.summary) <= 200
    assert doc.summary == long_content[:200].strip()


def test_create_document_validation_errors(db_session):
    """Empty titles or empty contents raise ValidationFailed."""
    with pytest.raises(ValidationFailed, match="title must be at least"):
        kb_service.create_document(db_session, title="", content="Valid content here")

    with pytest.raises(ValidationFailed, match="content cannot be empty"):
        kb_service.create_document(db_session, title="Valid Title", content="   ")


def test_reindex_document(db_session):
    """Reindexing updates the summary."""
    doc = kb_service.create_document(
        db_session,
        title="Initial Document",
        content="Paragraph one about loop closure.\n\nParagraph two about system architecture.",
        source_type=KBSource.DOCUMENT,
    )
    assert doc.summary is not None
    assert doc.index_status == "indexed"

    # Reindex
    updated = kb_service.reindex_document(db_session, doc.id)
    assert updated.id == doc.id
    assert updated.summary is not None
    assert updated.index_status == "indexed"


# ── Retrieval & Linking (Level A RAG) ─────────────────────────────────────────


def test_find_related_happy_path(db_session):
    """find_related() uses FakeProvider and returns LLM-scored matches >= 0.5."""
    doc1 = kb_service.create_document(
        db_session,
        title="FastAPI Guidelines",
        content="Best practices for using FastAPI with sync database sessions and typing.",
        source_type=KBSource.DOCUMENT,
    )
    doc2 = kb_service.create_document(
        db_session,
        title="PostgreSQL Setup",
        content="Configuring PostgreSQL for cloud deployment with SSL.",
        source_type=KBSource.DOCUMENT,
    )

    matches = retrieval.find_related(
        db_session,
        "We need to review our FastAPI routing structure",
        entity_type="meeting",
        entity_id=1,
    )
    assert len(matches) > 0
    # From FakeProvider: match has document_id=1 or 2, method='llm', score >= 0.5
    first = matches[0]
    assert first.method == "llm"
    assert first.score >= 0.5
    assert first.document_id in (doc1.id, doc2.id)


def test_find_related_keyword_fallback_on_ai_failure(db_session):
    """When the LLM fails, retrieval falls back to token-overlap keyword matching."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    # Create the document first while provider is normal
    doc = kb_service.create_document(
        db_session,
        title="Kubernetes Deployment Guide",
        content="Instructions for deploying containers onto Kubernetes clusters with Helm.",
        source_type=KBSource.DOCUMENT,
    )

    # Now set fail_mode to timeout to test fallback to keyword retriever
    provider.set_fail_mode("timeout")

    matches = retrieval.find_related(
        db_session,
        "Kubernetes deployment issues encountered",
        entity_type="meeting",
        entity_id=1,
    )
    assert len(matches) > 0
    assert matches[0].document_id == doc.id
    assert matches[0].method == "keyword"
    assert matches[0].score > 0.0


def test_link_lifecycle_and_uniqueness(db_session):
    """Links can be created, duplicate is idempotent, direct duplicate violates constraint, and deleted."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Elena", email="elena@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Design Sprint",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    doc = kb_service.create_document(
        db_session,
        title="Design System v2",
        content="Color palettes and typography guidelines for design system.",
        source_type=KBSource.DOCUMENT,
    )

    # 1. Create link
    link = kb_service.create_link(
        db_session,
        entity_type="meeting",
        entity_id=meeting.id,
        document_id=doc.id,
        reason="Reference design tokens",
        method=LinkMethod.MANUAL,
    )
    assert link.id is not None
    assert link.entity_type == "meeting"
    assert link.document_id == doc.id

    # 2. Duplicate link is idempotent (returns existing)
    dup = kb_service.create_link(
        db_session,
        entity_type="meeting",
        entity_id=meeting.id,
        document_id=doc.id,
        reason="Duplicate attempt",
        method=LinkMethod.MANUAL,
    )
    assert dup.id == link.id

    # 3. Direct duplicate insertion violates uq_kb_link unique constraint
    with pytest.raises(IntegrityError):
        db_session.add(
            KBLink(
                entity_type="meeting",
                entity_id=meeting.id,
                document_id=doc.id,
                reason="Constraint violation attempt",
                method="manual",
            )
        )
        db_session.flush()
    db_session.rollback()

    # 4. Retrieve links
    links = kb_service.get_entity_links(db_session, "meeting", meeting.id)
    assert len(links) == 1
    assert links[0].id == link.id

    # 5. Delete link
    assert kb_service.delete_link(db_session, link.id) is True
    assert len(kb_service.get_entity_links(db_session, "meeting", meeting.id)) == 0


def test_action_item_link_creates_audit_event(db_session):
    """Linking an action item to a document creates an append-only kb_linked audit event."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Rohan", email="rohan@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Sprint Planning",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(
            title="Review DB Schema",
            origin_meeting_id=meeting.id,
            owner_id=person.id,
            priority=Priority.HIGH,
        ),
    )
    doc = kb_service.create_document(
        db_session,
        title="Database ERD",
        content="Entity relationship diagram and migrations documentation.",
        source_type=KBSource.DOCUMENT,
    )

    kb_service.create_link(
        db_session,
        entity_type="action_item",
        entity_id=item.id,
        document_id=doc.id,
        reason="Required schema reference",
        method=LinkMethod.LLM,
    )

    # Check item events
    refreshed_item = action_item_service.get_action_item(db_session, item.id)
    kb_events = [e for e in refreshed_item.events if e.event_type == "kb_linked"]
    assert len(kb_events) == 1
    assert "Database ERD" in kb_events[0].to_value


# ── Auto-indexing Meetings to KB ──────────────────────────────────────────────


def test_auto_index_meeting_on_close(db_session):
    """Closing a meeting automatically creates or updates a KBDocument with source_type='meeting'."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Maya", email="maya@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Quarterly Review",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Discussion of Q3 deliverables. Decision: Proceed with Cloud migration.",
    )

    # Close meeting
    meeting_service.close_meeting(db_session, meeting.id)

    # Document should now exist in KB
    doc = (
        db_session.query(KBDocument)
        .filter(
            KBDocument.source_type == KBSource.MEETING.value,
            KBDocument.meeting_id == meeting.id,
        )
        .first()
    )
    assert doc is not None
    assert f"Meeting: {meeting.title}" in doc.title
    assert "Proceed with Cloud migration" in doc.content


# ── Catch-up Brief Service ───────────────────────────────────────────────────


def test_brief_default_person_selection(db_session):
    """Default person selection prioritizes absent > no_response > handover_to > first participant."""
    p1 = people_service.create_person(
        db_session, PersonCreate(name="Present User", email="present@example.com")
    )
    p2 = people_service.create_person(
        db_session, PersonCreate(name="Absent User", email="absent@example.com")
    )
    p3 = people_service.create_person(
        db_session, PersonCreate(name="NoResponse User", email="noresponse@example.com")
    )

    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Status Call",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[p1.id, p2.id, p3.id],
        ),
    )
    meeting_service.update_attendance(db_session, meeting.id, p1.id, Attendance.attended)
    meeting_service.update_attendance(db_session, meeting.id, p2.id, Attendance.absent)
    meeting_service.update_attendance(db_session, meeting.id, p3.id, Attendance.no_response)

    # Absent person must be chosen first
    target_id = brief_service.get_default_brief_person(meeting)
    assert target_id == p2.id


def test_generate_brief_happy_path(db_session):
    """AI happy path generates a structured brief stored in DB with generated_by='ai'."""
    p1 = people_service.create_person(
        db_session, PersonCreate(name="Target Person", email="target@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Weekly Retro",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[p1.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Sprint went smoothly. Team finished 18 story points. Decision: Next sprint starts Monday.",
    )

    brief = brief_service.generate_brief(db_session, meeting.id, p1.id)
    assert brief.id is not None
    assert brief.person_id == p1.id
    assert brief.generated_by == "ai"
    assert "tldr" in brief.content_json
    assert isinstance(brief.content_json["key_decisions"], list)
    assert isinstance(brief.content_json["your_items"], list)
    assert isinstance(brief.content_json["related_knowledge"], list)


def test_generate_brief_fallback_on_ai_failure(db_session):
    """When AI fails, generate_brief uses deterministic template brief with generated_by='fallback'."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    provider.set_fail_mode("timeout")

    p1 = people_service.create_person(
        db_session, PersonCreate(name="Catchup Lead", email="lead@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Critical Sync",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[p1.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Decision: Cut scope on analytics module.",
    )
    action_item_service.create_action_item(
        db_session,
        ActionItemCreate(
            title="Notify stakeholders of scope cut",
            origin_meeting_id=meeting.id,
            owner_id=p1.id,
            due_date=date.today(),
            priority=Priority.HIGH,
        ),
    )

    brief = brief_service.generate_brief(db_session, meeting.id, p1.id)
    assert brief.id is not None
    assert brief.generated_by == "fallback"
    assert "catch-up" in brief.content_json["tldr"].lower()
    assert len(brief.content_json["your_items"]) == 1
    assert "Notify stakeholders" in brief.content_json["your_items"][0]


# ── Web UI Endpoints ──────────────────────────────────────────────────────────


def test_web_kb_list_and_detail(client, db_session):
    """Test /kb and /kb/{id} web routes."""
    doc = kb_service.create_document(
        db_session,
        title="Web Doc Test",
        content="Content for testing the web route.",
        source_type=KBSource.DOCUMENT,
    )

    # 1. List route
    resp = client.get("/kb")
    assert resp.status_code == 200
    assert "Knowledge Base" in resp.text
    assert "Web Doc Test" in resp.text

    # Search filter
    search_resp = client.get("/kb?q=Web+Doc")
    assert search_resp.status_code == 200
    assert "Web Doc Test" in search_resp.text

    # 2. Detail route
    detail_resp = client.get(f"/kb/{doc.id}")
    assert detail_resp.status_code == 200
    assert "Web Doc Test" in detail_resp.text
    assert "Referenced By" in detail_resp.text


def test_web_kb_new_form_and_creation(client, db_session):
    """Test creating a KB document via /kb/new form and file upload."""
    # 1. Render form
    form_resp = client.get("/kb/new")
    assert form_resp.status_code == 200
    assert "Add Document to Knowledge Base" in form_resp.text

    # 2. Submit text form to /kb
    post_resp = client.post(
        "/kb",
        data={
            "title": "Created via Web Form",
            "source_type": "document",
            "content": "This is content submitted through the web form.",
        },
        follow_redirects=False,
    )
    assert post_resp.status_code == 303
    assert "/kb/" in post_resp.headers["location"]

    # 3. Submit valid file upload to /kb
    file_bytes = b"Markdown file content for automated tests."
    upload_resp = client.post(
        "/kb",
        data={"title": "Uploaded File Doc", "source_type": "document", "content": ""},
        files={"file": ("test_doc.md", io.BytesIO(file_bytes), "text/markdown")},
        follow_redirects=False,
    )
    assert upload_resp.status_code == 303


def test_web_kb_upload_validation(client):
    """File uploads exceeding 1MB or containing non-UTF8 bytes are rejected with 422."""
    # 1. Oversized file
    big_file = b"x" * (1024 * 1024 + 10)
    resp_big = client.post(
        "/kb",
        data={"title": "Big File", "source_type": "document", "content": ""},
        files={"file": ("big.txt", io.BytesIO(big_file), "text/plain")},
    )
    assert resp_big.status_code == 422
    assert "exceeds 1 MB" in resp_big.text

    # 2. Binary / invalid UTF-8 file
    invalid_utf8 = b"\x80\x81\xff\xfe"
    resp_bin = client.post(
        "/kb",
        data={"title": "Binary File", "source_type": "document", "content": ""},
        files={"file": ("bin.dat", io.BytesIO(invalid_utf8), "application/octet-stream")},
    )
    assert resp_bin.status_code == 422
    assert "valid UTF-8" in resp_bin.text


def test_web_suggest_and_create_link(client, db_session):
    """Test AI suggestion endpoint and link creation/deletion via web routes."""
    doc = kb_service.create_document(
        db_session,
        title="Deployment Architecture",
        content="Detailed deployment instructions on Render and Docker.",
        source_type=KBSource.DOCUMENT,
    )
    person = people_service.create_person(
        db_session, PersonCreate(name="Dev Lead", email="devlead@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Architecture Review",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    item = action_item_service.create_action_item(
        db_session,
        ActionItemCreate(
            title="Review Docker setup",
            origin_meeting_id=meeting.id,
            owner_id=person.id,
        ),
    )

    # 1. Suggest links for meeting
    m_sugg_resp = client.post(
        f"/meetings/{meeting.id}/suggest-links",
        headers={"HX-Request": "true"},
    )
    assert m_sugg_resp.status_code == 200
    assert "AI Suggested Related Knowledge" in m_sugg_resp.text

    # 2. Suggest links for action item
    i_sugg_resp = client.post(
        f"/items/{item.id}/suggest-links",
        headers={"HX-Request": "true"},
    )
    assert i_sugg_resp.status_code == 200
    assert "AI Suggested Related Knowledge" in i_sugg_resp.text

    # 3. Create link
    link_resp = client.post(
        "/links",
        data={
            "entity_type": "action_item",
            "entity_id": str(item.id),
            "document_id": str(doc.id),
            "reason": "Docker spec",
            "method": "llm",
        },
        follow_redirects=False,
    )
    assert link_resp.status_code == 303
    assert f"/items/{item.id}" in link_resp.headers["location"]

    # 4. Delete link
    link = (
        db_session.query(KBLink)
        .filter(KBLink.entity_type == "action_item", KBLink.entity_id == item.id)
        .first()
    )
    del_resp = client.post(
        f"/links/{link.id}/delete",
        data={"redirect_url": f"/items/{item.id}"},
        follow_redirects=False,
    )
    assert del_resp.status_code == 303
    assert f"/items/{item.id}" in del_resp.headers["location"]


def test_web_brief_generation(client, db_session):
    """Test generating a catch-up brief via POST /meetings/{id}/brief."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Brief User", email="briefuser@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Catchup Brief Web Test",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Team finalized release candidate. Everything is ready for staging.",
    )

    resp = client.post(
        f"/meetings/{meeting.id}/brief",
        data={"target_person_id": str(person.id)},
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "Personalized Catch-Up Brief" in resp.text
    assert "Copy Brief" in resp.text
    assert "Key Decisions" in resp.text
