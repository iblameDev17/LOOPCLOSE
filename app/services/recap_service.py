"""Recap service: generate AI recaps, resolve owners, and apply proposals.

This service coordinates between AIClient, prompts, fallbacks, and the domain
models to provide the full recap workflow: generate → review → apply/discard.
"""

from __future__ import annotations

import difflib
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.ai.client import AIClient, AIResult
from app.ai.fallbacks import heuristic_recap
from app.ai.prompts.recap import PROMPT_VERSION, build_prompt, build_system_prompt
from app.ai.schemas import RecapResult
from app.enums import AiStatus, EventType, ItemSource
from app.logging_config import log_event, request_id_var
from app.models.action_item import ActionItem, ActionItemEvent
from app.models.decision import Decision
from app.models.person import Person
from app.services import meeting_service

logger = logging.getLogger("app.ai")


def generate_recap(db: Session, meeting_id: int) -> dict:
    """Generate a structured recap from raw meeting notes.

    Returns the recap dict (matching RecapResult schema) and updates the
    meeting's ai_status, ai_error, and recap_json fields.
    Falls back to heuristic extraction if AI fails.
    """
    meeting = meeting_service.get_meeting(db, meeting_id)

    if not meeting.raw_notes or len(meeting.raw_notes.strip()) < 20:
        return {
            "error": "Notes must be at least 20 characters to generate a recap.",
            "ai_status": "failed",
        }

    # Gather participant names
    participant_names = [p.person.name for p in meeting.participants if p.person]

    # Build prompt
    system = build_system_prompt()
    prompt = build_prompt(
        raw_notes=meeting.raw_notes,
        agenda=meeting.agenda,
        participant_names=participant_names,
        meeting_date=meeting.scheduled_at,
    )

    # Call AI
    result: AIResult[RecapResult] = AIClient.run_structured(
        "recap",
        system=system,
        prompt=prompt,
        model_cls=RecapResult,
        prompt_version=PROMPT_VERSION,
    )

    if result.ok and result.data:
        recap_dict = result.data.model_dump(mode="json")
        # Resolve owners
        recap_dict["action_items"] = _resolve_owners(
            recap_dict.get("action_items", []),
            participant_names,
        )
        meeting.recap_json = recap_dict
        meeting.ai_status = AiStatus.OK.value
        meeting.ai_error = None
        meeting.summary = recap_dict.get("summary", "")
        db.commit()
        return recap_dict

    # Fallback to heuristic
    log_event(
        logger,
        "ai.fallback",
        level=logging.WARNING,
        operation="recap",
        reason=result.error_code or "unknown",
        fallback="heuristic",
    )
    fallback_dict = heuristic_recap(meeting.raw_notes)

    if not fallback_dict.get("action_items") and not fallback_dict.get("decisions"):
        # Nothing could be extracted
        meeting.ai_status = AiStatus.FAILED.value
        meeting.ai_error = f"AI failed ({result.error_code}); heuristic found nothing"
        meeting.recap_json = None
        db.commit()
        return {
            **fallback_dict,
            "ai_status": "failed",
            "ai_error": meeting.ai_error,
        }

    # Heuristic produced something useful
    fallback_dict["action_items"] = _resolve_owners(
        fallback_dict.get("action_items", []),
        participant_names,
    )
    meeting.recap_json = fallback_dict
    meeting.ai_status = AiStatus.FALLBACK.value
    meeting.ai_error = f"AI unavailable ({result.error_code}); using basic extraction"
    meeting.summary = fallback_dict.get("summary", "")
    db.commit()

    return {
        **fallback_dict,
        "ai_status": "fallback",
        "ai_error": meeting.ai_error,
    }


def _resolve_owners(
    items: list[dict],
    participant_names: list[str],
) -> list[dict]:
    """Resolve owner_name to a matching participant using exact then fuzzy matching.

    Per ARCHITECTURE.md §10.4: exact case-insensitive → difflib 0.8 → None.
    """
    if not participant_names:
        return items

    lower_names = {n.lower(): n for n in participant_names}

    for item in items:
        owner_name = item.get("owner_name")
        if not owner_name:
            item["resolved_owner"] = None
            item["owner_match"] = "none"
            continue

        owner_lower = owner_name.lower().strip()

        # Exact match
        if owner_lower in lower_names:
            item["resolved_owner"] = lower_names[owner_lower]
            item["owner_match"] = "exact"
            continue

        # Fuzzy match (cutoff 0.8)
        matches = difflib.get_close_matches(owner_lower, lower_names.keys(), n=1, cutoff=0.8)
        if matches:
            item["resolved_owner"] = lower_names[matches[0]]
            item["owner_match"] = "fuzzy"
            continue

        # No match
        item["resolved_owner"] = None
        item["owner_match"] = "none"

    return items


def apply_recap(
    db: Session,
    meeting_id: int,
    *,
    selected_decisions: list[int] | None = None,
    selected_items: list[int] | None = None,
    edited_summary: str | None = None,
) -> dict:
    """Apply selected rows from a recap proposal, creating decisions and items.

    Returns a summary of what was created.
    """
    meeting = meeting_service.get_meeting(db, meeting_id)
    recap = meeting.recap_json

    if not recap:
        return {"error": "No recap proposal to apply."}

    created_decisions = 0
    created_items = 0
    source = (
        ItemSource.AI.value
        if meeting.ai_status == AiStatus.OK.value
        else ItemSource.HEURISTIC.value
    )

    # Apply summary
    if edited_summary is not None:
        meeting.summary = edited_summary
    elif recap.get("summary"):
        meeting.summary = recap["summary"]

    # Apply selected decisions
    all_decisions = recap.get("decisions", [])
    indices_d = (
        set(selected_decisions)
        if selected_decisions is not None
        else set(range(len(all_decisions)))
    )
    for i, dec in enumerate(all_decisions):
        if i in indices_d:
            text = dec.get("text", "").strip()
            if text and len(text) >= 3:
                decision = Decision(
                    meeting_id=meeting_id,
                    text=text[:1000],
                    source=source,
                )
                db.add(decision)
                created_decisions += 1

    # Apply selected action items
    all_items = recap.get("action_items", [])
    indices_i = set(selected_items) if selected_items is not None else set(range(len(all_items)))

    # Build people lookup from participants
    people_by_name: dict[str, Person] = {}
    for p in meeting.participants:
        if p.person:
            people_by_name[p.person.name.lower()] = p.person

    for i, item_data in enumerate(all_items):
        if i not in indices_i:
            continue

        title = item_data.get("title", "").strip()
        if not title or len(title) < 3:
            continue

        # Resolve owner
        owner_id = None
        resolved_name = item_data.get("resolved_owner") or item_data.get("owner_name")
        if resolved_name:
            person = people_by_name.get(resolved_name.lower())
            if person:
                owner_id = person.id

        # Parse due date
        due_date = None
        raw_due = item_data.get("due_date")
        if raw_due:
            if isinstance(raw_due, str):
                try:
                    due_date = date.fromisoformat(raw_due)
                except ValueError:
                    due_date = None
            elif isinstance(raw_due, date):
                due_date = raw_due

        # Parse priority
        priority_str = item_data.get("priority", "medium")
        if priority_str not in ("low", "medium", "high"):
            priority_str = "medium"

        action_item = ActionItem(
            title=title[:200],
            description=item_data.get("rationale"),
            origin_meeting_id=meeting_id,
            current_meeting_id=meeting_id,
            owner_id=owner_id,
            due_date=due_date,
            priority=priority_str,
            status="open",
            source=source,
        )
        db.add(action_item)
        db.flush()

        # Create event
        event = ActionItemEvent(
            action_item_id=action_item.id,
            event_type=EventType.CREATED.value,
            actor="ai",
            to_value=title[:200],
            meeting_id=meeting_id,
            note=f"Created from {source} recap",
            request_id=request_id_var.get("-"),
        )
        db.add(event)
        created_items += 1

        log_event(
            logger,
            "item.created",
            item_id=action_item.id,
            origin_meeting_id=meeting_id,
            owner_id=owner_id,
            priority=priority_str,
            source=source,
        )

    db.commit()

    # Auto-index meeting into Knowledge Base per PRD FR-K2
    try:
        from app.services import kb_service

        kb_service.auto_index_meeting(db, meeting_id)
    except Exception as exc:
        logger.warning("Failed to auto-index meeting %s into KB: %s", meeting_id, exc)

    log_event(
        logger,
        "meeting.recap_applied",
        meeting_id=meeting_id,
        created_decisions=created_decisions,
        created_items=created_items,
        source=source,
    )

    return {
        "created_decisions": created_decisions,
        "created_items": created_items,
        "source": source,
    }


def discard_recap(db: Session, meeting_id: int) -> None:
    """Discard the current recap proposal without applying it."""
    meeting = meeting_service.get_meeting(db, meeting_id)
    meeting.recap_json = None
    meeting.ai_status = AiStatus.NONE.value
    meeting.ai_error = None
    db.commit()
