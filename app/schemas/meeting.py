"""Pydantic schemas for Meeting and MeetingParticipant."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums import Attendance, MeetingKind, MeetingStatus
from app.schemas.decision import DecisionRead
from app.schemas.person import PersonRead


class MeetingCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    kind: MeetingKind = Field(default=MeetingKind.MEETING)
    scheduled_at: datetime = Field(...)
    agenda: str | None = Field(default=None, max_length=5000)
    participant_ids: list[int] = Field(default_factory=list)

    # Handover fields
    handover_from_id: int | None = Field(default=None)
    handover_to_id: int | None = Field(default=None)

    # Carry forward support
    previous_meeting_id: int | None = Field(default=None)
    carry_forward_open_items: bool = Field(default=True)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Title must be at least 3 characters.")
        if len(s) > 200:
            raise ValueError("Title cannot exceed 200 characters.")
        return s

    @field_validator("agenda")
    @classmethod
    def validate_agenda(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 5000:
            raise ValueError("Agenda is too long (max 5,000).")
        return v

    @model_validator(mode="after")
    def validate_handover_and_participants(self) -> MeetingCreate:
        if self.kind == MeetingKind.HANDOVER:
            if not self.handover_from_id or not self.handover_to_id:
                raise ValueError("Choose both people for the handover.")
            if self.handover_from_id == self.handover_to_id:
                raise ValueError("Choose two different people.")
            # Ensure from and to are in participant_ids
            p_set = set(self.participant_ids)
            p_set.add(self.handover_from_id)
            p_set.add(self.handover_to_id)
            self.participant_ids = list(p_set)
        else:
            if not self.participant_ids:
                raise ValueError("Add at least one participant.")
        return self


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    scheduled_at: datetime | None = Field(default=None)
    agenda: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if len(s) < 3:
                raise ValueError("Title must be at least 3 characters.")
            if len(s) > 200:
                raise ValueError("Title cannot exceed 200 characters.")
            return s
        return v

    @field_validator("agenda")
    @classmethod
    def validate_agenda(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 5000:
            raise ValueError("Agenda is too long (max 5,000).")
        return v


class MeetingStatusUpdate(BaseModel):
    status: MeetingStatus


class NotesUpdate(BaseModel):
    raw_notes: str = Field(default="", max_length=50000)

    @field_validator("raw_notes")
    @classmethod
    def validate_raw_notes(cls, v: str) -> str:
        if len(v) > 50000:
            raise ValueError("Raw notes cannot exceed 50,000 characters.")
        return v


class ParticipantAttendanceUpdate(BaseModel):
    person_id: int
    attendance: Attendance


class ParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    person_id: int
    attendance: str
    person: PersonRead


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    status: str
    scheduled_at: datetime
    agenda: str | None
    raw_notes: str | None
    summary: str | None
    ai_status: str
    ai_error: str | None
    recap_json: dict[str, Any] | None
    previous_meeting_id: int | None
    handover_from_id: int | None
    handover_to_id: int | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    participants: list[ParticipantRead] = []
    decisions: list[DecisionRead] = []
    handover_from: PersonRead | None = None
    handover_to: PersonRead | None = None
