"""Podřízený záznam průběhu kontroly státního dozoru."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class StateSupervisionTimelineItem(Base):
    __tablename__ = "state_supervision_timeline_items"
    __table_args__ = (
        Index(
            "ix_state_supervision_timeline_items_list",
            "state_supervision_id",
            "active",
            "display_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_supervision_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("state_supervisions.id"),
        nullable=False,
        index=True,
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    place: Mapped[str | None] = mapped_column(String(250), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
