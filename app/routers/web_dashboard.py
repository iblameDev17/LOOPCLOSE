"""
Placeholder dashboard router.

This file will be replaced in Unit 3/4 with real dashboard logic.
For Unit 1 it renders the base layout so we can verify the CSS works.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    """Render the placeholder dashboard page."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"page_title": "Dashboard"},
    )
