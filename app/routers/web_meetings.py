"""Web router for Meetings and Handovers."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import Attendance, MeetingKind
from app.errors import ValidationFailed
from app.models.decision import Decision
from app.schemas.meeting import MeetingCreate
from app.services import meeting_service, people_service

router = APIRouter(tags=["meetings"])
templates = Jinja2Templates(directory="app/templates")


def _get_base_context(request: Request, db: Session) -> dict:
    all_people = people_service.list_people(db, active_only=False)
    raw_cookie = request.cookies.get("loopclose_view_as")
    viewing_as_id = int(raw_cookie) if raw_cookie and raw_cookie.isdigit() else None
    return {
        "request": request,
        "people": all_people,
        "viewing_as_id": viewing_as_id,
    }


@router.get("/meetings", response_class=HTMLResponse)
def list_meetings_view(
    request: Request,
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the filterable meetings and handovers list."""
    ctx = _get_base_context(request, db)
    meetings = meeting_service.list_meetings(db, kind=kind, status=status)
    ctx.update(
        {
            "meetings": meetings,
            "current_kind": kind,
            "current_status": status,
            "page_title": "Meetings & Handovers",
        }
    )
    return templates.TemplateResponse(request=request, name="meetings/list.html", context=ctx)


@router.get("/meetings/new", response_class=HTMLResponse)
def new_meeting_view(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the new meeting / handover form."""
    ctx = _get_base_context(request, db)
    active_people = people_service.list_people(db, active_only=True)
    recent_meetings = meeting_service.list_meetings(db)[:10]
    ctx.update(
        {
            "active_people": active_people,
            "recent_meetings": recent_meetings,
            "page_title": "New Meeting",
        }
    )
    return templates.TemplateResponse(request=request, name="meetings/form.html", context=ctx)


@router.post("/meetings", response_class=HTMLResponse)
def create_meeting_action(
    request: Request,
    title: Annotated[str, Form()],
    scheduled_at: Annotated[str, Form()],
    kind: Annotated[str, Form()] = "meeting",
    agenda: Annotated[str, Form()] = "",
    participant_ids: Annotated[list[int] | None, Form()] = None,
    handover_from_id: Annotated[str, Form()] = "",
    handover_to_id: Annotated[str, Form()] = "",
    previous_meeting_id: Annotated[str, Form()] = "",
    carry_forward_open_items: Annotated[bool, Form()] = True,
    db: Session = Depends(get_db),
) -> Response:
    """Create meeting or handover."""
    actual_participant_ids = participant_ids or []
    ctx = _get_base_context(request, db)
    active_people = people_service.list_people(db, active_only=True)
    recent_meetings = meeting_service.list_meetings(db)[:10]
    ctx.update(
        {
            "active_people": active_people,
            "recent_meetings": recent_meetings,
            "page_title": "New Meeting",
        }
    )

    try:
        sched_dt = datetime.fromisoformat(scheduled_at)
    except (ValueError, TypeError):
        ctx["error"] = "Pick a valid date and time."
        ctx["form_data"] = {
            "title": title,
            "kind": kind,
            "scheduled_at": scheduled_at,
            "agenda": agenda,
            "participant_ids": [str(p) for p in actual_participant_ids],
            "handover_from_id": handover_from_id,
            "handover_to_id": handover_to_id,
            "previous_meeting_id": previous_meeting_id,
        }
        res = templates.TemplateResponse(request=request, name="meetings/form.html", context=ctx)
        res.status_code = 422
        return res

    from_id = int(handover_from_id) if handover_from_id.isdigit() else None
    to_id = int(handover_to_id) if handover_to_id.isdigit() else None
    prev_id = int(previous_meeting_id) if previous_meeting_id.isdigit() else None

    try:
        meeting_kind = MeetingKind(kind)
        data = MeetingCreate(
            title=title,
            kind=meeting_kind,
            scheduled_at=sched_dt,
            agenda=agenda.strip() or None,
            participant_ids=actual_participant_ids,
            handover_from_id=from_id,
            handover_to_id=to_id,
            previous_meeting_id=prev_id,
            carry_forward_open_items=carry_forward_open_items,
        )
        created = meeting_service.create_meeting(db, data)
    except (ValidationError, ValidationFailed) as exc:
        msg = exc.message if hasattr(exc, "message") else str(exc)
        ctx["error"] = msg
        ctx["form_data"] = {
            "title": title,
            "kind": kind,
            "scheduled_at": scheduled_at,
            "agenda": agenda,
            "participant_ids": [str(p) for p in actual_participant_ids],
            "handover_from_id": handover_from_id,
            "handover_to_id": handover_to_id,
            "previous_meeting_id": previous_meeting_id,
        }
        res = templates.TemplateResponse(request=request, name="meetings/form.html", context=ctx)
        res.status_code = 422
        return res

    return RedirectResponse(url=f"/meetings/{created.id}", status_code=303)


@router.get("/meetings/{id}", response_class=HTMLResponse)
def meeting_detail_view(
    request: Request,
    id: int,
    tab: str = Query(default="overview"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render meeting detail page or individual tab partial."""
    meeting = meeting_service.get_meeting(db, id)
    ctx = _get_base_context(request, db)
    all_people = people_service.list_people(db, active_only=True)
    existing_pids = {p.person_id for p in meeting.participants}

    ctx.update(
        {
            "meeting": meeting,
            "active_tab": tab,
            "all_people": all_people,
            "existing_participant_ids": existing_pids,
            "page_title": meeting.title,
        }
    )

    if request.headers.get("HX-Request") == "true":
        tab_templates = {
            "overview": "meetings/partials/overview_tab.html",
            "notes": "meetings/partials/notes_tab.html",
            "items": "meetings/partials/items_tab.html",
            "brief": "meetings/partials/brief_tab.html",
            "knowledge": "meetings/partials/knowledge_tab.html",
            "history": "meetings/partials/history_tab.html",
        }
        tpl = tab_templates.get(tab, "meetings/partials/overview_tab.html")
        return templates.TemplateResponse(request=request, name=tpl, context=ctx)

    return templates.TemplateResponse(request=request, name="meetings/detail.html", context=ctx)


@router.post("/meetings/{id}/status")
def change_meeting_status(
    request: Request,
    id: int,
    status: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Change meeting status."""
    meeting_service.update_meeting_status(db, id, status)
    return RedirectResponse(url=f"/meetings/{id}", status_code=303)


@router.post("/meetings/{id}/notes", response_class=HTMLResponse)
def save_meeting_notes(
    request: Request,
    id: int,
    raw_notes: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> Response:
    """Save raw notes for a meeting."""
    meeting = meeting_service.save_notes(db, id, raw_notes)
    if request.headers.get("HX-Request") == "true":
        ctx = _get_base_context(request, db)
        ctx["meeting"] = meeting
        return templates.TemplateResponse(
            request=request, name="meetings/partials/notes_tab.html", context=ctx
        )
    return RedirectResponse(url=f"/meetings/{id}?tab=notes", status_code=303)


@router.post("/meetings/{id}/participants", response_class=HTMLResponse)
def add_meeting_participant(
    request: Request,
    id: int,
    person_id: Annotated[int, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Add a participant to the meeting."""
    try:
        meeting_service.add_participant(db, id, person_id)
    except ValidationFailed:
        pass  # Silently ignore if already a participant

    if request.headers.get("HX-Request") == "true":
        meeting = meeting_service.get_meeting(db, id)
        ctx = _get_base_context(request, db)
        ctx.update(
            {
                "meeting": meeting,
                "all_people": people_service.list_people(db, active_only=True),
                "existing_participant_ids": {p.person_id for p in meeting.participants},
            }
        )
        return templates.TemplateResponse(
            request=request, name="meetings/partials/participants_card.html", context=ctx
        )
    return RedirectResponse(url=f"/meetings/{id}?tab=overview", status_code=303)


@router.post("/meetings/{id}/participants/attendance", response_class=HTMLResponse)
def update_attendance(
    request: Request,
    id: int,
    person_id: Annotated[int, Form()],
    attendance: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Update participant attendance record."""
    meeting_service.update_participant_attendance(db, id, person_id, Attendance(attendance))

    if request.headers.get("HX-Request") == "true":
        meeting = meeting_service.get_meeting(db, id)
        ctx = _get_base_context(request, db)
        ctx.update(
            {
                "meeting": meeting,
                "all_people": people_service.list_people(db, active_only=True),
                "existing_participant_ids": {p.person_id for p in meeting.participants},
            }
        )
        return templates.TemplateResponse(
            request=request, name="meetings/partials/participants_card.html", context=ctx
        )
    return RedirectResponse(url=f"/meetings/{id}?tab=overview", status_code=303)


@router.post("/meetings/{id}/decisions", response_class=HTMLResponse)
def add_meeting_decision(
    request: Request,
    id: int,
    text: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Add a key decision to the meeting."""
    meeting_service.add_decision(db, id, text)
    if request.headers.get("HX-Request") == "true":
        meeting = meeting_service.get_meeting(db, id)
        ctx = _get_base_context(request, db)
        ctx["meeting"] = meeting
        return templates.TemplateResponse(
            request=request, name="meetings/partials/decisions_list.html", context=ctx
        )
    return RedirectResponse(url=f"/meetings/{id}?tab=overview", status_code=303)


@router.post("/decisions/{id}/delete", response_class=HTMLResponse)
def delete_meeting_decision(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a key decision."""
    decision = db.get(Decision, id)
    meeting_id = decision.meeting_id if decision else None
    if decision:
        meeting_service.delete_decision(db, id)

    if request.headers.get("HX-Request") == "true" and meeting_id:
        meeting = meeting_service.get_meeting(db, meeting_id)
        ctx = _get_base_context(request, db)
        ctx["meeting"] = meeting
        return templates.TemplateResponse(
            request=request, name="meetings/partials/decisions_list.html", context=ctx
        )
    return RedirectResponse(
        url=f"/meetings/{meeting_id}" if meeting_id else "/meetings", status_code=303
    )


@router.post("/meetings/{id}/handover/reassign")
def handover_reassign(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Bulk reassign handover items (stub)."""
    meeting_service.reassign_handover_items_stub(db, id)
    return RedirectResponse(url=f"/meetings/{id}?tab=overview", status_code=303)
