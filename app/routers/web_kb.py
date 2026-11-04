"""Web router for Knowledge Base documents and links."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import KBSource, LinkMethod
from app.errors import ValidationFailed
from app.services import kb_service, people_service

router = APIRouter(tags=["knowledge-base"])
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


@router.get("/kb", response_class=HTMLResponse)
def list_documents_view(
    request: Request,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render the Knowledge Base document catalogue."""
    ctx = _get_base_context(request, db)
    documents = kb_service.list_documents(db, query=q)
    ctx.update(
        {
            "documents": documents,
            "query": q or "",
            "page_title": "Team Knowledge Base",
        }
    )
    return templates.TemplateResponse(request=request, name="kb/list.html", context=ctx)


@router.get("/kb/new", response_class=HTMLResponse)
def new_document_view(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render form to create or upload a new KB document."""
    ctx = _get_base_context(request, db)
    ctx.update(
        {
            "sources": [s.value for s in KBSource],
            "page_title": "Add Document",
        }
    )
    return templates.TemplateResponse(request=request, name="kb/form.html", context=ctx)


@router.post("/kb", response_class=HTMLResponse)
@router.post("/kb/new", response_class=HTMLResponse)
def create_document_action(
    request: Request,
    title: Annotated[str, Form()] = "",
    source_type: Annotated[str, Form()] = "document",
    content: Annotated[str, Form()] = "",
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Create a new document by text paste or file upload."""
    ctx = _get_base_context(request, db)
    ctx.update({"sources": [s.value for s in KBSource], "page_title": "Add Document"})

    final_content = content.strip()

    # Handle file upload if provided
    if file and file.filename:
        # Check size (1MB limit)
        file_bytes = file.file.read()
        if len(file_bytes) > 1024 * 1024:
            ctx["error"] = "Uploaded file exceeds 1 MB limit."
            ctx["form_data"] = {"title": title, "source_type": source_type, "content": content}
            res = templates.TemplateResponse(request=request, name="kb/form.html", context=ctx)
            res.status_code = 422
            return res

        # Validate UTF-8
        try:
            file_text = file_bytes.decode("utf-8")
            final_content = file_text.strip()
            if not title.strip():
                # Derive title from filename
                title = file.filename.rsplit(".", 1)[0].replace("_", " ").title()
        except UnicodeDecodeError:
            ctx["error"] = "File must be valid UTF-8 plain text or Markdown."
            ctx["form_data"] = {"title": title, "source_type": source_type, "content": content}
            res = templates.TemplateResponse(request=request, name="kb/form.html", context=ctx)
            res.status_code = 422
            return res

    try:
        doc = kb_service.create_document(
            db,
            title=title,
            content=final_content,
            source_type=KBSource(source_type)
            if source_type in [s.value for s in KBSource]
            else KBSource.DOCUMENT,
        )
    except ValidationFailed as exc:
        ctx["error"] = exc.message
        ctx["form_data"] = {"title": title, "source_type": source_type, "content": content}
        res = templates.TemplateResponse(request=request, name="kb/form.html", context=ctx)
        res.status_code = 422
        return res

    return RedirectResponse(url=f"/kb/{doc.id}", status_code=303)


@router.get("/kb/{id}", response_class=HTMLResponse)
def document_detail_view(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Render single document detail with referenced-by section."""
    doc = kb_service.get_document(db, id)
    referrers = kb_service.get_document_referrers(db, id)
    ctx = _get_base_context(request, db)
    ctx.update(
        {
            "doc": doc,
            "referrers": referrers,
            "page_title": doc.title,
        }
    )
    return templates.TemplateResponse(request=request, name="kb/detail.html", context=ctx)


@router.post("/kb/{id}/reindex")
def reindex_document_action(
    id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Re-summarize and index a document."""
    kb_service.reindex_document(db, id)
    return RedirectResponse(url=f"/kb/{id}", status_code=303)


# ── Linking Management Endpoints ──────────────────────────────────────────────


@router.post("/links", response_class=HTMLResponse)
def create_link_action(
    request: Request,
    entity_type: Annotated[str, Form()],
    entity_id: Annotated[int, Form()],
    document_id: Annotated[int, Form()],
    reason: Annotated[str, Form()] = "",
    method: Annotated[str, Form()] = "manual",
    db: Session = Depends(get_db),
) -> Response:
    """Manually add or accept an AI suggestion link."""
    kb_service.create_link(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        document_id=document_id,
        reason=reason.strip() or "Manual link",
        method=LinkMethod(method) if method in [m.value for m in LinkMethod] else LinkMethod.MANUAL,
    )

    # Return redirect or HTMX partial if needed
    if entity_type == "meeting":
        return RedirectResponse(url=f"/meetings/{entity_id}?tab=knowledge", status_code=303)
    elif entity_type == "action_item":
        return RedirectResponse(url=f"/items/{entity_id}", status_code=303)
    return RedirectResponse(url="/kb", status_code=303)


@router.post("/links/{id}/delete")
def delete_link_action(
    id: int,
    redirect_url: Annotated[str, Form()] = "/kb",
    db: Session = Depends(get_db),
) -> Response:
    """Delete an existing link."""
    kb_service.delete_link(db, id)
    return RedirectResponse(url=redirect_url, status_code=303)
