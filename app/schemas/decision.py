"""Pydantic schemas for Decision."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ItemSource


class DecisionCreate(BaseModel):
    text: str = Field(..., min_length=3, max_length=1000)
    source: ItemSource = Field(default=ItemSource.MANUAL)

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Decision text must be at least 3 characters.")
        if len(s) > 1000:
            raise ValueError("Decision text cannot exceed 1000 characters.")
        return s


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    text: str
    source: str
    created_at: datetime
