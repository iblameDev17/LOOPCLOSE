"""Pydantic schemas for Person."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Person full name")
    email: str | None = Field(
        default=None, max_length=200, description="Optional valid email address"
    )
    role_title: str | None = Field(default=None, max_length=100, description="Optional role/title")
    is_active: bool = Field(default=True, description="Active status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name is required.")
        if len(s) > 100:
            raise ValueError("Name cannot exceed 100 characters.")
        return s

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        if not s:
            return None
        if "@" not in s or "." not in s.split("@")[-1]:
            raise ValueError("Invalid email address format.")
        if len(s) > 200:
            raise ValueError("Email cannot exceed 200 characters.")
        return s


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None
    role_title: str | None
    is_active: bool
    created_at: datetime

    @property
    def initials(self) -> str:
        parts = self.name.strip().split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
