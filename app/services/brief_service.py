"""Brief service: generates and persists personalized catch-up briefs."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import AIClient, AIResult
from app.ai.prompts.brief import PROMPT_VERSION, build_prompt, build_system_prompt
from app.ai.schemas import BriefResult
from app.enums import Attendance, EventType, GeneratedBy
from app.errors import NotFoundError
from app.logging_config import log_event
from app.models.brief import CatchupBrief
from app.models.meeting import Meeting
from app.models.person import Person
from app.services import kb_service

logger = logging.getLogger("app.meetings")


def get_default_brief_person(
    meeting_or_db: Session | Meeting, meeting: Meeting | None = None
) -> int | None:
    """Choose default person for brief: absent -> no_response -> handover_to -> first participant."""
    target_meeting: Meeting = (
        meeting if meeting is not None else meeting_or_db  # type: ignore[assignment]
    )
    if target_meeting.is_handover and target_meeting.handover_to_id:
        return target_meeting.handover_to_id

    # Find first absent or no_response participant
    for p in target_meeting.participants:
        if p.attendance in (Attendance.ABSENT.value, Attendance.NO_RESPONSE.value):
            return p.person_id

    # Fallback to first participant
    if target_meeting.participants:
        return target_meeting.participants[0].person_id

    return None


def generate_brief(
    db: Session,
    meeting_id: int,
    person_id: int,
) -> CatchupBrief:
    """Generate or regenerate a personalized catch-up brief."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise NotFoundError(f"Meeting with id {meeting_id} not found.")

    person = db.get(Person, person_id)
    if not person:
        raise NotFoundError(f"Person with id {person_id} not found.")

    # 1. Assemble structured context
    context = _assemble_context(db, meeting, person)

    # 2. Call AI
    system = build_system_prompt()
    prompt = build_prompt(context=context)

    result: AIResult[BriefResult] = AIClient.run_structured(
        "brief",
        system=system,
        prompt=prompt,
        model_cls=BriefResult,
        prompt_version=PROMPT_VERSION,
    )

    if result.ok and result.data:
        brief_data = result.data.model_dump(mode="json")
        gen_by = GeneratedBy.AI.value
    else:
        # Fallback template brief
        log_event(
            logger,
            "ai.fallback",
            level=logging.WARNING,
            operation="brief",
            reason=result.error_code or "unknown",
            fallback="template",
        )
        brief_data = _build_template_brief(meeting, person, context)
        gen_by = GeneratedBy.FALLBACK.value

    # 3. Persist CatchupBrief (replace existing for same meeting & person if present)
    existing = db.scalar(
        select(CatchupBrief).where(
            CatchupBrief.meeting_id == meeting_id,
            CatchupBrief.person_id == person_id,
        )
    )
    if existing:
        existing.content_json = brief_data
        existing.generated_by = gen_by
        brief = existing
    else:
        brief = CatchupBrief(
            meeting_id=meeting_id,
            person_id=person_id,
            content_json=brief_data,
            generated_by=gen_by,
        )
        db.add(brief)

    db.commit()
    db.refresh(brief)

    log_event(
        logger,
        "meeting.brief_generated",
        meeting_id=meeting_id,
        person_id=person_id,
        generated_by=gen_by,
    )
    return brief


def get_brief(db: Session, meeting_id: int, person_id: int) -> CatchupBrief | None:
    """Retrieve existing brief for a person and meeting."""
    return db.scalar(
        select(CatchupBrief).where(
            CatchupBrief.meeting_id == meeting_id,
            CatchupBrief.person_id == person_id,
        )
    )


def _assemble_context(db: Session, meeting: Meeting, person: Person) -> dict:
    """Build rich context for AI or template generation."""
    decisions = [d.text for d in meeting.decisions]

    # Person's open items
    person_items = [
        f"{it.title} (due: {it.due_date or 'None'}, priority: {it.priority})"
        for it in meeting.current_items
        if it.owner_id == person.id
    ]

    # Changes / Events
    changed_since: list[str] = []
    for it in meeting.current_items:
        for ev in it.events:
            if ev.event_type in (
                EventType.REASSIGNED.value,
                EventType.CARRIED_FORWARD.value,
                EventType.BLOCKED.value,
            ):
                changed_since.append(f"{it.title}: {ev.event_type} ({ev.note or ''})")

    # Related knowledge documents
    links = kb_service.get_entity_links(db, "meeting", meeting.id)
    related_kb = [
        {
            "document_id": lk.document_id,
            "title": lk.document.title if lk.document else f"Doc #{lk.document_id}",
            "why": lk.reason,
        }
        for lk in links
    ]

    return {
        "meeting_title": meeting.title,
        "meeting_kind": meeting.kind,
        "meeting_date": meeting.scheduled_at.strftime("%A, %d %B %Y"),
        "reader_name": person.name,
        "reader_role": person.role_title or "Team member",
        "summary": meeting.summary or "No summary recorded.",
        "agenda": meeting.agenda or "",
        "decisions": decisions,
        "your_items": person_items,
        "changed_since": changed_since[:10],
        "related_knowledge": related_kb[:3],
    }


def _build_template_brief(meeting: Meeting, person: Person, context: dict) -> dict:
    """Assemble deterministic template brief when AI is unavailable."""
    summary = meeting.summary or "Discussion was held and key points were addressed."
    tldr = f"Catch-up for {person.name} on '{meeting.title}'. {summary}"

    steps = []
    if context["your_items"]:
        steps.append("Review your assigned action items.")
    if meeting.decisions:
        steps.append("Acknowledge key decisions from the meeting.")
    steps.append("Reach out to meeting participants if you have questions.")

    return {
        "tldr": tldr,
        "key_decisions": context["decisions"],
        "your_items": context["your_items"],
        "changed_since": context["changed_since"],
        "open_questions": [],
        "related_knowledge": context["related_knowledge"],
        "suggested_first_steps": steps[:5],
    }
