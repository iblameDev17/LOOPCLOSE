"""Knowledge Base service: documents, summarization, auto-indexing, and linking."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.ai.client import AIClient, AIResult
from app.ai.prompts.kb_summary import PROMPT_VERSION, build_prompt, build_system_prompt
from app.ai.schemas import KBSummarizeResult
from app.enums import EventType, IndexStatus, KBSource, LinkMethod
from app.errors import NotFoundError, ValidationFailed
from app.logging_config import log_event, request_id_var
from app.models.action_item import ActionItem, ActionItemEvent
from app.models.kb import KBDocument, KBLink
from app.models.meeting import Meeting

logger = logging.getLogger("app.kb")


def list_documents(db: Session, query: str | None = None) -> list[KBDocument]:
    """List documents with optional search in title and content."""
    stmt = select(KBDocument).order_by(KBDocument.updated_at.desc())
    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                KBDocument.title.ilike(q),
                KBDocument.content.ilike(q),
                KBDocument.summary.ilike(q),
            )
        )
    return list(db.scalars(stmt).all())


def get_document(db: Session, doc_id: int) -> KBDocument:
    """Retrieve document by ID or raise NotFoundError."""
    stmt = select(KBDocument).options(joinedload(KBDocument.links)).where(KBDocument.id == doc_id)
    doc = db.execute(stmt).unique().scalar_one_or_none()
    if not doc:
        raise NotFoundError(f"KBDocument with id {doc_id} not found.")
    return doc


def create_document(
    db: Session,
    title: str,
    content: str,
    source_type: str | KBSource = KBSource.DOCUMENT,
    meeting_id: int | None = None,
) -> KBDocument:
    """Create a new KB document, generate AI summary and tags, and log event."""
    clean_title = title.strip()
    if len(clean_title) < 3:
        raise ValidationFailed("Document title must be at least 3 characters.", field="title")
    if len(clean_title) > 200:
        raise ValidationFailed("Document title cannot exceed 200 characters.", field="title")

    clean_content = content.strip()
    if not clean_content:
        raise ValidationFailed("Document content cannot be empty.", field="content")
    if len(clean_content) > 100000:
        raise ValidationFailed(
            "Document content cannot exceed 100,000 characters.", field="content"
        )

    src_val = source_type.value if hasattr(source_type, "value") else str(source_type)

    # Generate summary & tags
    summary, tags = _summarize_document(clean_content)

    doc = KBDocument(
        title=clean_title,
        content=clean_content,
        source_type=src_val,
        summary=summary,
        tags=tags,
        meeting_id=meeting_id,
        index_status=IndexStatus.INDEXED.value if summary else IndexStatus.PENDING.value,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_event(
        logger,
        "kb.document_created",
        document_id=doc.id,
        title=doc.title,
        source_type=doc.source_type,
        content_length=len(doc.content),
    )
    return doc


def _summarize_document(content: str) -> tuple[str, list[str]]:
    """Generate summary & tags via AI, with deterministic first-200-chars fallback."""
    system = build_system_prompt()
    prompt = build_prompt(content[:12000])

    result: AIResult[KBSummarizeResult] = AIClient.run_structured(
        "kb_summarize",
        system=system,
        prompt=prompt,
        model_cls=KBSummarizeResult,
        prompt_version=PROMPT_VERSION,
    )

    if result.ok and result.data:
        return result.data.summary.strip(), result.data.tags

    # Fallback per ARCHITECTURE.md §10.3: first 200 chars as summary, tags empty
    trimmed = content[:200].strip()
    return trimmed, []


def reindex_document(db: Session, doc_id: int) -> KBDocument:
    """Re-summarize and refresh a document."""
    doc = get_document(db, doc_id)
    summary, tags = _summarize_document(doc.content)
    doc.summary = summary
    doc.tags = tags
    doc.index_status = IndexStatus.INDEXED.value
    doc.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(doc)
    log_event(logger, "kb.summarized", document_id=doc.id)
    return doc


def auto_index_meeting(db: Session, meeting_id: int) -> KBDocument | None:
    """Auto-index a past meeting as a KB document (type meeting).

    Refreshes existing document if one already exists for this meeting.
    """
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return None

    # Construct unified content
    parts = [
        f"# {meeting.title}",
        f"Scheduled: {meeting.scheduled_at.strftime('%d %B %Y, %H:%M UTC')}",
    ]
    if meeting.summary:
        parts.append(f"## Summary\n{meeting.summary}")
    if meeting.agenda:
        parts.append(f"## Agenda\n{meeting.agenda}")
    if meeting.decisions:
        dec_texts = "\n".join(f"- {d.text}" for d in meeting.decisions)
        parts.append(f"## Key Decisions\n{dec_texts}")
    if meeting.current_items:
        items_texts = "\n".join(
            f"- [{it.priority.upper()}] {it.title} (Status: {it.status})"
            for it in meeting.current_items
        )
        parts.append(f"## Action Items\n{items_texts}")
    if meeting.raw_notes:
        parts.append(f"## Raw Notes\n{meeting.raw_notes[:5000]}")

    content = "\n\n".join(parts)
    title = f"Meeting: {meeting.title}"

    # Check if document already exists for this meeting
    existing = db.scalar(select(KBDocument).where(KBDocument.meeting_id == meeting_id))

    if existing:
        existing.title = title
        existing.content = content
        summary, tags = _summarize_document(content)
        existing.summary = summary
        existing.tags = list(set(tags + ["meeting"]))
        existing.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(existing)
        return existing

    return create_document(
        db,
        title=title,
        content=content,
        source_type=KBSource.MEETING,
        meeting_id=meeting_id,
    )


# ── Linking Management ────────────────────────────────────────────────────────


def create_link(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    document_id: int,
    reason: str = "",
    method: str | LinkMethod = LinkMethod.MANUAL,
    score: float = 1.0,
    actor: str = "user",
) -> KBLink:
    """Link an entity to a KB document (enforcing uniqueness)."""
    # Verify document exists
    doc = db.get(KBDocument, document_id)
    if not doc:
        raise NotFoundError(f"KBDocument with id {document_id} not found.")

    # Check uniqueness
    existing = db.scalar(
        select(KBLink).where(
            KBLink.entity_type == entity_type,
            KBLink.entity_id == entity_id,
            KBLink.document_id == document_id,
        )
    )
    if existing:
        return existing

    method_val = method.value if hasattr(method, "value") else str(method)
    link = KBLink(
        entity_type=entity_type,
        entity_id=entity_id,
        document_id=document_id,
        reason=reason[:300] if reason else "Linked reference",
        method=method_val,
        score=score,
    )
    db.add(link)
    db.flush()

    # If linked to an action item, record kb_linked audit event
    if entity_type == "action_item":
        item = db.get(ActionItem, entity_id)
        if item:
            event = ActionItemEvent(
                action_item_id=item.id,
                event_type=EventType.KB_LINKED.value,
                actor=actor,
                to_value=doc.title[:200],
                note=f"Linked to '{doc.title}' ({method_val}): {reason[:200]}",
                meeting_id=item.current_meeting_id,
                request_id=request_id_var.get("-"),
            )
            db.add(event)

    db.commit()
    db.refresh(link)

    log_event(
        logger,
        "kb.link_created",
        link_id=link.id,
        entity_type=entity_type,
        entity_id=entity_id,
        document_id=document_id,
        method=method_val,
    )
    return link


def delete_link(db: Session, link_id: int) -> bool:
    """Delete a link by ID."""
    link = db.get(KBLink, link_id)
    if not link:
        raise NotFoundError(f"KBLink with id {link_id} not found.")
    db.delete(link)
    db.commit()
    return True


def get_entity_links(db: Session, entity_type: str, entity_id: int) -> list[KBLink]:
    """Get all links attached to an entity with document loaded."""
    stmt = (
        select(KBLink)
        .options(joinedload(KBLink.document))
        .where(KBLink.entity_type == entity_type, KBLink.entity_id == entity_id)
        .order_by(KBLink.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_document_referrers(db: Session, doc_id: int) -> list[KBLink]:
    """Get all links pointing to a specific document."""
    stmt = select(KBLink).where(KBLink.document_id == doc_id).order_by(KBLink.created_at.desc())
    return list(db.scalars(stmt).all())
