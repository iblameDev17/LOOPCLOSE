"""CatchupBrief model for personalized meeting/handover briefs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import GeneratedBy

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.person import Person


class CatchupBrief(Base):
    __tablename__ = "catchup_briefs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_by: Mapped[str] = mapped_column(
        String(20), default=GeneratedBy.AI.value, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    meeting: Mapped[Meeting] = relationship("Meeting")
    person: Mapped[Person] = relationship("Person")
