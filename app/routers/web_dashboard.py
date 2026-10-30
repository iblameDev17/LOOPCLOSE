"""Web router for the main dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.decision import Decision
from app.services import action_item_service, meeting_service, people_service

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the dashboard page wired with real data."""
    all_people = people_service.list_people(db, active_only=False)
    raw_cookie = request.cookies.get("loopclose_view_as")
    viewing_as_id = int(raw_cookie) if raw_cookie and raw_cookie.isdigit() else None
    viewing_person = db.get(people_service.Person, viewing_as_id) if viewing_as_id else None

    # My open items
    if viewing_as_id:
        my_open_items = [
            it
            for it in action_item_service.list_action_items(db, owner_id=viewing_as_id)
            if it.is_open
        ][:5]
    else:
        my_open_items = [it for it in action_item_service.list_action_items(db) if it.is_open][:5]

    # Needs attention counts
    all_items = action_item_service.list_action_items(db)
    overdue_count = sum(1 for it in all_items if it.is_overdue)
    needs_owner_count = sum(1 for it in all_items if it.is_open and not it.owner_id)

    # Upcoming meetings (next 7 days)
    now = datetime.now(UTC)
    meetings = meeting_service.list_meetings(db)
    upcoming_meetings = [
        m for m in meetings if not m.is_closed and m.scheduled_at >= (now - timedelta(hours=2))
    ][:5]

    # Recent decisions
    decisions_stmt = (
        select(Decision)
        .options(joinedload(Decision.meeting))
        .order_by(Decision.created_at.desc())
        .limit(8)
    )
    recent_decisions = list(db.execute(decisions_stmt).scalars().all())

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "page_title": "Dashboard",
            "people": all_people,
            "viewing_as_id": viewing_as_id,
            "viewing_person": viewing_person,
            "my_open_items": my_open_items,
            "overdue_count": overdue_count,
            "needs_owner_count": needs_owner_count,
            "upcoming_meetings": upcoming_meetings,
            "recent_decisions": recent_decisions,
        },
    )
