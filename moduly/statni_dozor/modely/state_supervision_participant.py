"""Podřízený účastník kontroly státního dozoru."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class StateSupervisionParticipant(Base):
    __tablename__ = "state_supervision_participants"
    __table_args__ = (
        Index(
            "ix_state_supervision_participants_list",
            "state_supervision_id",
            "active",
            "display_order",
        ),
        Index(
            "ix_state_supervision_participants_source",
            "source_type",
            "source_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_supervision_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("state_supervisions.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(250), nullable=False)
    organization_snapshot: Mapped[str | None] = mapped_column(
        String(250), nullable=True
    )
    contact_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    planned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    attendance_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
