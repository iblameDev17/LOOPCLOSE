"""Person model representing a team member."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.action_item import ActionItem
    from app.models.meeting import Meeting, MeetingParticipant


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    participations: Mapped[list[MeetingParticipant]] = relationship(
        "MeetingParticipant", back_populates="person", cascade="all, delete-orphan"
    )
    handovers_from: Mapped[list[Meeting]] = relationship(
        "Meeting",
        foreign_keys="Meeting.handover_from_id",
        back_populates="handover_from",
    )
    handovers_to: Mapped[list[Meeting]] = relationship(
        "Meeting",
        foreign_keys="Meeting.handover_to_id",
        back_populates="handover_to",
    )
    owned_items: Mapped[list[ActionItem]] = relationship(
        "ActionItem",
        foreign_keys="ActionItem.owner_id",
        back_populates="owner",
    )

    @property
    def initials(self) -> str:
        parts = self.name.strip().split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
