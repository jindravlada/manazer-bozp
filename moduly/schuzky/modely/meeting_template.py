"""Šablona události – opakovaně použitelná struktura."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class MeetingTemplate(Base):
    __tablename__ = "meeting_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    event_type: Mapped[str] = mapped_column(String(100), default="Schůzka", nullable=False)
    title: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    location: Mapped[str] = mapped_column(String(250), default="")
    priority: Mapped[str] = mapped_column(String(30), default="Normální", nullable=False)

    organizer_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    organizer_source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    organizer_source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON: legacy [person_id, ...] nebo [{"source_type","source_id"}, ...]
    participant_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    external_participants_json: Mapped[str] = mapped_column(Text, default="[]")

    # Body zápisků: title, moje_sdeleni, status (bez průběhu, závěru, úkolů).
    agenda_items_json: Mapped[str] = mapped_column(Text, default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
