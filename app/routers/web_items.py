"""Web router for Action Items."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import ActionStatus, OutcomeType, Priority
from app.errors import ValidationFailed
from app.schemas.action_item import (
    ActionItemClose,
    ActionItemCreate,
    ActionItemUpdate,
)
from app.services import (
    action_item_service,
    carry_forward_service,
    meeting_service,
    people_service,
)

router = APIRouter(tags=["items"])
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


@router.get("/items", response_class=HTMLResponse)
def list_items_view(
    request: Request,
    status: str | None = Query(default=None),
    owner_id: int | None = Query(default=None),
    meeting_id: int | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    sort_by: str = Query(default="due_date"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the global action items list with filters."""
    ctx = _get_base_context(request, db)
    items = action_item_service.list_action_items(
        db,
        status=status,
        owner_id=owner_id,
        meeting_id=meeting_id,
        is_overdue=overdue,
        sort_by=sort_by,
    )
    all_meetings = meeting_service.list_meetings(db)[:20]

    ctx.update(
        {
            "items": items,
            "current_status": status,
            "current_owner_id": owner_id,
            "current_meeting_id": meeting_id,
            "current_overdue": overdue,
            "sort_by": sort_by,
            "all_meetings": all_meetings,
            "total_count": len(items),
            "page_title": "Action Items",
        }
    )
    return templates.TemplateResponse(request=request, name="items/list.html", context=ctx)


@router.post("/items")
def create_item_action(
    request: Request,
    title: Annotated[str, Form()],
    origin_meeting_id: Annotated[int, Form()],
    description: Annotated[str, Form()] = "",
    owner_id: Annotated[str, Form()] = "",
    due_date: Annotated[str, Form()] = "",
    priority: Annotated[str, Form()] = "medium",
    db: Session = Depends(get_db),
) -> Response:
    """Create a new action item."""
    parsed_owner_id = int(owner_id) if owner_id.isdigit() else None
    parsed_due_date = None
    if due_date.strip():
        try:
            parsed_due_date = date.fromisoformat(due_date.strip())
        except ValueError:
            parsed_due_date = None

    try:
        data = ActionItemCreate(
            title=title,
            description=description.strip() or None,
            origin_meeting_id=origin_meeting_id,
            current_meeting_id=origin_meeting_id,
            owner_id=parsed_owner_id,
            due_date=parsed_due_date,
            priority=Priority(priority),
        )
        action_item_service.create_action_item(db, data)
    except (ValidationError, ValidationFailed) as exc:
        msg = exc.message if hasattr(exc, "message") else str(exc)
        if request.headers.get("HX-Request") == "true":
            ctx = _get_base_context(request, db)
            meeting = meeting_service.get_meeting(db, origin_meeting_id)
            active_people = people_service.list_people(db, active_only=True)
            ctx.update(
                {
                    "meeting": meeting,
                    "active_people": active_people,
                    "error": msg,
                    "form_data": {
                        "title": title,
                        "description": description,
                        "owner_id": owner_id,
                        "due_date": due_date,
                        "priority": priority,
                    },
                }
            )
            res = templates.TemplateResponse(
                request=request, name="meetings/partials/items_tab.html", context=ctx
            )
            res.status_code = 422
            return res
        return RedirectResponse(url=f"/meetings/{origin_meeting_id}?tab=items", status_code=303)

    if request.headers.get("HX-Request") == "true":
        ctx = _get_base_context(request, db)
        meeting = meeting_service.get_meeting(db, origin_meeting_id)
        active_people = people_service.list_people(db, active_only=True)
        ctx.update({"meeting": meeting, "active_people": active_people})
        return templates.TemplateResponse(
            request=request, name="meetings/partials/items_tab.html", context=ctx
        )

    return RedirectResponse(url=f"/meetings/{origin_meeting_id}?tab=items", status_code=303)


@router.get("/items/{id}", response_class=HTMLResponse)
def item_detail_view(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render item detail page with side card, actions, and history timeline."""
    item = action_item_service.get_action_item(db, id)
    ctx = _get_base_context(request, db)
    active_people = people_service.list_people(db, active_only=True)

    ctx.update(
        {
            "item": item,
            "active_people": active_people,
            "page_title": f"Item #{item.id}: {item.title}",
        }
    )
    return templates.TemplateResponse(request=request, name="items/detail.html", context=ctx)


@router.post("/items/{id}/close")
def close_item_action(
    request: Request,
    id: int,
    outcome_type: Annotated[str, Form()],
    outcome_note: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Close an item with outcome type and note."""
    try:
        data = ActionItemClose(
            outcome_type=OutcomeType(outcome_type),
            outcome_note=outcome_note,
        )
        action_item_service.close_action_item(db, id, data)
    except (ValidationError, ValidationFailed) as exc:
        msg = exc.message if hasattr(exc, "message") else str(exc)
        if request.headers.get("HX-Request") == "true":
            item = action_item_service.get_action_item(db, id)
            ctx = _get_base_context(request, db)
            active_people = people_service.list_people(db, active_only=True)
            ctx.update({"item": item, "active_people": active_people, "close_error": msg})
            res = templates.TemplateResponse(request=request, name="items/detail.html", context=ctx)
            res.status_code = 422
            return res
        return RedirectResponse(url=f"/items/{id}", status_code=303)

    return RedirectResponse(url=f"/items/{id}", status_code=303)


@router.post("/items/{id}/status")
def update_status_action(
    request: Request,
    id: int,
    status: Annotated[str, Form()],
    blocked_reason: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> Response:
    """Transition between open, in_progress, and blocked."""
    action_item_service.change_status(
        db,
        id,
        new_status=ActionStatus(status),
        blocked_reason=blocked_reason.strip() or None,
    )
    return RedirectResponse(url=f"/items/{id}", status_code=303)


@router.post("/items/{id}/reassign")
def reassign_item_action(
    request: Request,
    id: int,
    owner_id: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> Response:
    """Reassign owner of the item."""
    parsed_id = int(owner_id) if owner_id.isdigit() else None
    action_item_service.reassign_action_item(db, id, parsed_id)
    return RedirectResponse(url=f"/items/{id}", status_code=303)


@router.post("/items/{id}/reopen")
def reopen_item_action(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Reopen a closed item."""
    action_item_service.reopen_action_item(db, id)
    return RedirectResponse(url=f"/items/{id}", status_code=303)


@router.post("/items/{id}/edit")
def edit_item_action(
    request: Request,
    id: int,
    title: Annotated[str, Form()] = "",
    due_date: Annotated[str, Form()] = "",
    priority: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
) -> Response:
    """Edit item details."""
    parsed_due = None
    if due_date.strip():
        try:
            parsed_due = date.fromisoformat(due_date.strip())
        except ValueError:
            pass

    data = ActionItemUpdate(
        title=title.strip() or None,
        due_date=parsed_due,
        priority=Priority(priority) if priority else None,
        description=description.strip() or None,
    )
    action_item_service.update_action_item(db, id, data)
    return RedirectResponse(url=f"/items/{id}", status_code=303)


@router.post("/meetings/{id}/carry-forward")
def carry_forward_action(
    request: Request,
    id: int,
    target_meeting_id: Annotated[int, Form()],
    db: Session = Depends(get_db),
) -> Response:
    """Carry forward open items from this meeting to a target meeting."""
    carry_forward_service.carry_forward_items(
        db, source_meeting_id=id, target_meeting_id=target_meeting_id
    )
    return RedirectResponse(url=f"/meetings/{target_meeting_id}?tab=overview", status_code=303)
