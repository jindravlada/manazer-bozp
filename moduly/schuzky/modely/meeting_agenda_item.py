"""Bod jednání schůzky."""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class MeetingAgendaItem(Base):
    """Strukturovaný bod jednání (téma) v rámci schůzky."""

    __tablename__ = "meeting_agenda_items"
    __table_args__ = (Index("ix_meeting_agenda_items_meeting_id", "meeting_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(Integer, nullable=False)

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    title: Mapped[str] = mapped_column(String(250), default="", nullable=False)
