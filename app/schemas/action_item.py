"""Pydantic schemas for ActionItem and ActionItemEvent validation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import ActionStatus, ItemSource, OutcomeType, Priority


class ActionItemCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Title must be 3-200 characters",
    )
    description: str | None = Field(default=None, max_length=5000)
    origin_meeting_id: int
    current_meeting_id: int | None = None
    owner_id: int | None = None
    due_date: date | None = None
    priority: Priority = Priority.MEDIUM
    source: ItemSource = ItemSource.MANUAL

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Give the item a short title (3+ characters).")
        return s

    @field_validator("due_date")
    @classmethod
    def validate_due_date_not_past(cls, v: date | None) -> date | None:
        if v is not None and v < date.today():
            raise ValueError("Due date can't be in the past.")
        return v


class ActionItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    owner_id: int | None = None
    due_date: date | None = None
    priority: Priority | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Give the item a short title (3+ characters).")
        return s


class ActionItemClose(BaseModel):
    outcome_type: OutcomeType = Field(
        ..., description="Completed, partially completed, dropped, superseded"
    )
    outcome_note: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Record the outcome before closing (5+ chars)",
    )

    @field_validator("outcome_note")
    @classmethod
    def validate_outcome_note(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 5:
            raise ValueError("Record the outcome before closing.")
        return s


class ActionItemReassign(BaseModel):
    new_owner_id: int | None = None


class ActionItemStatusUpdate(BaseModel):
    status: ActionStatus
    blocked_reason: str | None = Field(default=None, max_length=300)

    @field_validator("blocked_reason")
    @classmethod
    def validate_blocked(cls, v: str | None, info) -> str | None:
        status = info.data.get("status")
        if status in (ActionStatus.BLOCKED, ActionStatus.BLOCKED.value, "blocked"):
            s = (v or "").strip()
            if len(s) < 3:
                raise ValueError("Say what is blocking this.")
            return s
        return v


class ActionItemEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_item_id: int
    event_type: str
    actor: str
    from_value: str | None = None
    to_value: str | None = None
    meeting_id: int | None = None
    note: str | None = None
    created_at: datetime


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    origin_meeting_id: int
    current_meeting_id: int | None = None
    owner_id: int | None = None
    due_date: date | None = None
    priority: str
    status: str
    blocked_reason: str | None = None
    outcome_type: str | None = None
    outcome_note: str | None = None
    source: str
    carried_count: int
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_open: bool
    is_overdue: bool
