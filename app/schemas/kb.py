"""Pydantic schemas for Knowledge Base and Briefs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import GeneratedBy, KBSource, LinkMethod


class KBDocumentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    source_type: KBSource = KBSource.DOCUMENT
    content: str = Field(..., min_length=1, max_length=100000)


class KBDocumentRead(BaseModel):
    id: int
    title: str
    source_type: str
    summary: str | None = None
    tags: list[str] = []
    meeting_id: int | None = None
    index_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KBLinkCreate(BaseModel):
    entity_type: str
    entity_id: int
    document_id: int
    score: float = 1.0
    reason: str = Field("", max_length=300)
    method: LinkMethod = LinkMethod.MANUAL


class KBLinkRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    document_id: int
    score: float
    reason: str
    method: str
    created_at: datetime
    document_title: str | None = None

    model_config = {"from_attributes": True}


class CatchupBriefRead(BaseModel):
    id: int
    meeting_id: int
    person_id: int
    content_json: dict
    generated_by: GeneratedBy
    created_at: datetime

    model_config = {"from_attributes": True}
