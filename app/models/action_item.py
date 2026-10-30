"""ActionItem and ActionItemEvent models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import ActionStatus, EventType, ItemSource, Priority

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.person import Person


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    origin_meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    current_meeting_id: Mapped[int | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default=Priority.MEDIUM.value, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ActionStatus.OPEN.value, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    outcome_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default=ItemSource.MANUAL.value, nullable=False)
    carried_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

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
    origin_meeting: Mapped[Meeting] = relationship(
        "Meeting", foreign_keys=[origin_meeting_id], back_populates="origin_items"
    )
    current_meeting: Mapped[Meeting | None] = relationship(
        "Meeting", foreign_keys=[current_meeting_id], back_populates="current_items"
    )
    owner: Mapped[Person | None] = relationship(
        "Person", foreign_keys=[owner_id], back_populates="owned_items"
    )
    events: Mapped[list[ActionItemEvent]] = relationship(
        "ActionItemEvent", back_populates="action_item", cascade="all, delete-orphan"
    )

    @property
    def is_open(self) -> bool:
        return self.status in (
            ActionStatus.OPEN.value,
            ActionStatus.IN_PROGRESS.value,
            ActionStatus.BLOCKED.value,
        )

    @property
    def is_overdue(self) -> bool:
        if self.due_date is None or not self.is_open:
            return False
        return self.due_date < date.today()


class ActionItemEvent(Base):
    __tablename__ = "action_item_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action_item_id: Mapped[int] = mapped_column(
        ForeignKey("action_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(30), default=EventType.CREATED.value, nullable=False
    )
    actor: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    from_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meeting_id: Mapped[int | None] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String(32), default="-", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    action_item: Mapped[ActionItem] = relationship("ActionItem", back_populates="events")
