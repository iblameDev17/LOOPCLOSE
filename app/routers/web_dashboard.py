"""
Placeholder dashboard router.

This file will be replaced in Unit 3/4 with real dashboard logic.
For Unit 1 it renders the base layout so we can verify the CSS works.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import people_service

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the dashboard page."""
    all_people = people_service.list_people(db, active_only=False)
    raw_cookie = request.cookies.get("loopclose_view_as")
    viewing_as_id = int(raw_cookie) if raw_cookie and raw_cookie.isdigit() else None
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "page_title": "Dashboard",
            "people": all_people,
            "viewing_as_id": viewing_as_id,
        },
    )
