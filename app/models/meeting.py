"""Meeting and MeetingParticipant models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import AiStatus, Attendance, MeetingKind, MeetingStatus

if TYPE_CHECKING:
    from app.models.action_item import ActionItem
    from app.models.decision import Decision
    from app.models.person import Person


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), default=MeetingKind.MEETING.value, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=MeetingStatus.PLANNED.value, nullable=False
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agenda: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(20), default=AiStatus.NONE.value, nullable=False)
    ai_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    recap_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    previous_meeting_id: Mapped[int | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    handover_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    handover_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    participants: Mapped[list[MeetingParticipant]] = relationship(
        "MeetingParticipant", back_populates="meeting", cascade="all, delete-orphan"
    )
    decisions: Mapped[list[Decision]] = relationship(
        "Decision", back_populates="meeting", cascade="all, delete-orphan"
    )
    handover_from: Mapped[Person | None] = relationship(
        "Person", foreign_keys=[handover_from_id], back_populates="handovers_from"
    )
    handover_to: Mapped[Person | None] = relationship(
        "Person", foreign_keys=[handover_to_id], back_populates="handovers_to"
    )
    previous_meeting: Mapped[Meeting | None] = relationship(
        "Meeting", remote_side=[id], foreign_keys=[previous_meeting_id]
    )

    current_items: Mapped[list[ActionItem]] = relationship(
        "ActionItem",
        foreign_keys="ActionItem.current_meeting_id",
        back_populates="current_meeting",
    )
    origin_items: Mapped[list[ActionItem]] = relationship(
        "ActionItem",
        foreign_keys="ActionItem.origin_meeting_id",
        back_populates="origin_meeting",
    )

    @property
    def is_closed(self) -> bool:
        return self.status in (MeetingStatus.CLOSED.value, MeetingStatus.CANCELLED.value)

    @property
    def is_handover(self) -> bool:
        return self.kind == MeetingKind.HANDOVER.value


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "person_id", name="uq_meeting_participant"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    attendance: Mapped[str] = mapped_column(
        String(20), default=Attendance.INVITED.value, nullable=False
    )

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="participants")
    person: Mapped[Person] = relationship("Person", back_populates="participations")
