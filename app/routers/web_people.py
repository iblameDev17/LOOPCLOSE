"""Web router for People management and the Viewing As selector."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import ValidationFailed
from app.schemas.person import PersonCreate
from app.services import people_service

router = APIRouter(tags=["people"])
templates = Jinja2Templates(directory="app/templates")


def _get_viewing_as_context(request: Request, db: Session) -> dict:
    """Helper to inject people and viewing_as_id into template context."""
    all_people = people_service.list_people(db, active_only=False)
    raw_cookie = request.cookies.get("loopclose_view_as")
    viewing_as_id = int(raw_cookie) if raw_cookie and raw_cookie.isdigit() else None
    return {
        "people": all_people,
        "viewing_as_id": viewing_as_id,
    }


@router.get("/people", response_class=HTMLResponse)
def list_people_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the People list and creation page."""
    ctx = _get_viewing_as_context(request, db)
    ctx.update(
        {
            "request": request,
            "page_title": "People",
        }
    )
    return templates.TemplateResponse(request=request, name="people/index.html", context=ctx)


@router.post("/people", response_class=HTMLResponse)
def create_person_action(
    request: Request,
    name: Annotated[str, Form()],
    email: Annotated[str, Form()] = "",
    role_title: Annotated[str, Form()] = "",
    is_active: Annotated[bool, Form()] = True,
    db: Session = Depends(get_db),
) -> Response:
    """Create a new person."""
    ctx = _get_viewing_as_context(request, db)
    ctx.update({"request": request, "page_title": "People"})

    clean_email = email.strip() or None
    try:
        data = PersonCreate(
            name=name,
            email=clean_email,  # type: ignore[arg-type]
            role_title=role_title.strip() or None,
            is_active=is_active,
        )
        people_service.create_person(db, data)
    except (ValidationError, ValidationFailed) as exc:
        msg = exc.message if hasattr(exc, "message") else str(exc)
        ctx["error"] = msg
        ctx["form_data"] = {
            "name": name,
            "email": email,
            "role_title": role_title,
            "is_active": is_active,
        }
        res = templates.TemplateResponse(request=request, name="people/index.html", context=ctx)
        res.status_code = 422
        return res

    if request.headers.get("HX-Request") == "true":
        response = Response(status_code=200)
        response.headers["HX-Refresh"] = "true"
        return response

    return RedirectResponse(url="/people", status_code=303)


@router.post("/viewing-as")
def set_viewing_as(
    request: Request,
    person_id: Annotated[str, Form()] = "",
) -> Response:
    """Set or clear the viewing-as cookie."""
    pid = person_id.strip()
    if request.headers.get("HX-Request") == "true":
        response = Response(status_code=200)
        response.headers["HX-Refresh"] = "true"
    else:
        referer = request.headers.get("Referer", "/")
        response = RedirectResponse(url=referer, status_code=303)

    if pid and pid.isdigit():
        response.set_cookie(
            key="loopclose_view_as",
            value=pid,
            max_age=30 * 86400,
            samesite="lax",
            httponly=False,
        )
    else:
        response.delete_cookie(key="loopclose_view_as")

    return response
