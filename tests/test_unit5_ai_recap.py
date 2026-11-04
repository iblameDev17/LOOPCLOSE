"""Unit 5 tests — AI foundation, client, prompts, fallbacks, recap service, and web UI.

All tests MUST use FakeProvider and run 100% offline without hitting the network (AGENTS.md §6.8).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.ai.client import AIClient, _strip_fences, get_provider, reset_provider
from app.ai.fake import FakeProvider
from app.ai.fallbacks import heuristic_recap
from app.ai.prompts.recap import PROMPT_VERSION, build_prompt, build_system_prompt
from app.ai.schemas import RecapResult
from app.enums import AiStatus, EventType, ItemSource, MeetingKind
from app.schemas.meeting import MeetingCreate
from app.schemas.person import PersonCreate
from app.services import meeting_service, people_service, recap_service


@pytest.fixture(autouse=True)
def setup_fake_provider():
    """Ensure FakeProvider is used and clean between tests."""
    reset_provider()
    provider = get_provider()
    if isinstance(provider, FakeProvider):
        provider.set_fail_mode(None)
        provider.call_count = 0
    yield
    reset_provider()


# ── Code-fence stripping ──────────────────────────────────────────────────────


def test_strip_fences():
    """AIClient strips markdown ```json and ``` code fences."""
    raw = '```json\n{"summary": "Test", "decisions": []}\n```'
    assert _strip_fences(raw) == '{"summary": "Test", "decisions": []}'

    bare = '{"summary": "Test", "decisions": []}'
    assert _strip_fences(bare) == bare


# ── AIClient & FakeProvider ───────────────────────────────────────────────────


def test_ai_client_valid_json():
    """Happy path: valid JSON returns AIResult(ok=True) with parsed model."""
    result = AIClient.run_structured(
        "recap",
        system=build_system_prompt(),
        prompt="Sample meeting notes",
        model_cls=RecapResult,
        prompt_version=PROMPT_VERSION,
    )
    assert result.ok is True
    assert result.data is not None
    assert len(result.data.decisions) == 1
    assert result.data.decisions[0].text == "Deploy to production by end of week"
    assert result.attempts == 1


def test_ai_client_timeout_fallback():
    """Timeout error in provider results in ok=False and recorded error code."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    provider.set_fail_mode("timeout")

    result = AIClient.run_structured(
        "recap",
        system=build_system_prompt(),
        prompt="Notes",
        model_cls=RecapResult,
    )
    assert result.ok is False
    assert result.error_code == "timeout"
    assert result.data is None


def test_ai_client_invalid_json_fallback():
    """Invalid JSON retries and returns ok=False on repeated failure."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    provider.set_fail_mode("invalid_json")

    result = AIClient.run_structured(
        "recap",
        system=build_system_prompt(),
        prompt="Notes",
        model_cls=RecapResult,
    )
    assert result.ok is False
    assert result.error_code == "invalid_json"
    assert result.attempts == 2  # 1 initial + 1 retry


# ── Heuristic Fallback ────────────────────────────────────────────────────────


def test_heuristic_recap_extraction():
    """Heuristic recap parses lines with Action:, TODO, - [ ], AI:, Decision:."""
    notes = """
    Team sync notes. We reviewed sprint goals.
    Decision: Use PostgreSQL in production.
    Action: Write database migration scripts
    TODO: Review pull requests by tomorrow
    - [ ] Set up monitoring alerts
    AI: Benchmark query performance
    What is the target SLA?
    """
    fallback = heuristic_recap(notes)

    assert len(fallback["decisions"]) == 1
    assert fallback["decisions"][0]["text"] == "Use PostgreSQL in production."

    assert len(fallback["action_items"]) == 4
    titles = [item["title"] for item in fallback["action_items"]]
    assert "Write database migration scripts" in titles
    assert "Review pull requests by tomorrow" in titles
    assert "Set up monitoring alerts" in titles
    assert "Benchmark query performance" in titles

    assert "What is the target SLA?" in fallback["open_questions"]
    assert "Team sync notes." in fallback["summary"]


# ── Prompt Generation ─────────────────────────────────────────────────────────


def test_prompt_includes_meeting_date_and_participants():
    """Prompt must include relative meeting date and participant list."""
    meeting_dt = datetime(2026, 11, 6, 10, 30, tzinfo=UTC)
    prompt = build_prompt(
        raw_notes="Fix login bug by Friday",
        agenda="Sprint sync",
        participant_names=["Aarav", "Sneha"],
        meeting_date=meeting_dt,
    )
    assert "06 November 2026" in prompt
    assert "Aarav, Sneha" in prompt
    assert "Sprint sync" in prompt
    assert "<notes>" in prompt
    assert "Fix login bug by Friday" in prompt


# ── Owner Resolution (Exact, Fuzzy, None) ─────────────────────────────────────


def test_owner_resolution_exact_fuzzy_none():
    """Owner matching: exact case-insensitive -> fuzzy >=0.8 -> none."""
    items = [
        {"title": "Task 1", "owner_name": "aarav"},
        {"title": "Task 2", "owner_name": "Snehaa"},  # close match to Sneha
        {"title": "Task 3", "owner_name": "Unknown Person"},
        {"title": "Task 4", "owner_name": None},
    ]
    participants = ["Aarav", "Sneha"]

    resolved = recap_service._resolve_owners(items, participants)

    assert resolved[0]["owner_match"] == "exact"
    assert resolved[0]["resolved_owner"] == "Aarav"

    assert resolved[1]["owner_match"] == "fuzzy"
    assert resolved[1]["resolved_owner"] == "Sneha"

    assert resolved[2]["owner_match"] == "none"
    assert resolved[2]["resolved_owner"] is None

    assert resolved[3]["owner_match"] == "none"
    assert resolved[3]["resolved_owner"] is None


# ── Recap Service Workflow (Generate, Apply, Discard) ─────────────────────────


def test_generate_recap_happy_path(db_session):
    """Generate recap produces proposal, sets ai_status=ok, and stores recap_json."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Aarav", email="aarav@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Design Review",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Discussion on architecture. Decision: Ship on Friday. Action: Aarav to deploy scripts.",
    )

    recap = recap_service.generate_recap(db_session, meeting.id)

    db_session.refresh(meeting)
    assert meeting.ai_status == AiStatus.OK.value
    assert meeting.recap_json is not None
    assert "summary" in recap
    assert len(recap["decisions"]) >= 1


def test_generate_recap_fallback_on_failure(db_session):
    """When AI fails, generate_recap falls back to heuristic and sets ai_status=fallback."""
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    provider.set_fail_mode("timeout")

    person = people_service.create_person(
        db_session, PersonCreate(name="Sneha", email="sneha@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Incident Postmortem",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Postmortem meeting notes.\nDecision: Implement health checks.\nAction: Sneha to update alert rules.",
    )

    recap = recap_service.generate_recap(db_session, meeting.id)

    db_session.refresh(meeting)
    assert meeting.ai_status == AiStatus.FALLBACK.value
    assert len(recap["decisions"]) == 1
    assert recap["decisions"][0]["text"] == "Implement health checks."
    assert len(recap["action_items"]) == 1


def test_apply_recap_creates_items_and_decisions(db_session):
    """Applying recap creates Decision and ActionItem rows with source=ai and audit events."""
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

    meeting.recap_json = {
        "summary": "Agreed on sprint scope.",
        "decisions": [{"text": "Freeze scope today"}],
        "action_items": [
            {
                "title": "Set up CI pipeline",
                "owner_name": "Rohan",
                "resolved_owner": "Rohan",
                "due_date": str(date.today()),
                "priority": "high",
                "rationale": "Required before sprint kickoff",
            }
        ],
        "open_questions": [],
    }
    meeting.ai_status = AiStatus.OK.value
    db_session.commit()

    result = recap_service.apply_recap(db_session, meeting.id)

    assert result["created_decisions"] == 1
    assert result["created_items"] == 1
    assert result["source"] == ItemSource.AI.value

    db_session.refresh(meeting)
    assert len(meeting.decisions) == 1
    assert meeting.decisions[0].text == "Freeze scope today"
    assert meeting.decisions[0].source == ItemSource.AI.value

    assert len(meeting.current_items) == 1
    item = meeting.current_items[0]
    assert item.title == "Set up CI pipeline"
    assert item.owner_id == person.id
    assert item.priority == "high"
    assert item.source == ItemSource.AI.value

    # Verify history event created with actor=ai
    assert len(item.events) == 1
    assert item.events[0].event_type == EventType.CREATED.value
    assert item.events[0].actor == "ai"


def test_discard_recap(db_session):
    """Discarding recap clears recap_json and resets ai_status to none."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Priya", email="priya@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="Sync",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting.recap_json = {"summary": "Temporary recap"}
    meeting.ai_status = AiStatus.OK.value
    db_session.commit()

    recap_service.discard_recap(db_session, meeting.id)

    db_session.refresh(meeting)
    assert meeting.recap_json is None
    assert meeting.ai_status == AiStatus.NONE.value


# ── Web UI Endpoints ──────────────────────────────────────────────────────────


def test_web_generate_and_apply_recap(client, db_session):
    """Test web recap endpoints: /meetings/{id}/recap and /meetings/{id}/recap/apply."""
    person = people_service.create_person(
        db_session, PersonCreate(name="Aarav", email="aarav.ui@example.com")
    )
    meeting = meeting_service.create_meeting(
        db_session,
        MeetingCreate(
            title="UI Recap Test",
            kind=MeetingKind.MEETING,
            scheduled_at=datetime.now(UTC),
            participant_ids=[person.id],
        ),
    )
    meeting_service.save_notes(
        db_session,
        meeting.id,
        "Team discussion about roadmap. Decision: Ship Q1 roadmap. Action: Finalize specifications.",
    )

    # 1. Generate recap
    resp = client.post(f"/meetings/{meeting.id}/recap", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "Review Recap Proposal" in resp.text
    assert "Deploy to production by end of week" in resp.text  # from FakeProvider canned recap

    # 2. Apply recap
    apply_resp = client.post(
        f"/meetings/{meeting.id}/recap/apply",
        data={
            "summary": "Approved summary.",
            "selected_decisions": ["0"],
            "selected_items": ["0"],
        },
        headers={"HX-Request": "true"},
    )
    assert apply_resp.status_code == 200
    assert "Recap applied!" in apply_resp.text
