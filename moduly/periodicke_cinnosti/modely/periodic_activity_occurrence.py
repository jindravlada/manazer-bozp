"""Historický záznam provedení periodické činnosti (immutable po vytvoření)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class PeriodicActivityOccurrence(Base):
    __tablename__ = "periodic_activity_occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    activity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    planned_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    performed_at: Mapped[date] = mapped_column(Date, nullable=False)

    performed_by_kind: Mapped[str] = mapped_column(String(20), default="")
    performed_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    performed_by_name: Mapped[str] = mapped_column(String(150), default="")

    result_note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
