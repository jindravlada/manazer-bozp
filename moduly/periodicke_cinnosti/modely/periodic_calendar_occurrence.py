"""Výjimka jednoho výskytu pevné kalendářní řady.

Řádný výskyt se neukládá. Řádek vznikne až při přesunu, stavu
„Nevykoná se“ nebo pozdější vazbě na úkol či událost.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.periodicke_cinnosti.constants import CALENDAR_STATUS_TO_PLAN


class PeriodicCalendarOccurrence(Base):
    __tablename__ = "periodic_calendar_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "original_year",
            "original_month",
            name="uq_periodic_calendar_occurrence_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    activity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    original_year: Mapped[int] = mapped_column(Integer, nullable=False)
    original_month: Mapped[int] = mapped_column(Integer, nullable=False)

    display_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    display_month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(30),
        default=CALENDAR_STATUS_TO_PLAN,
        nullable=False,
    )
    skip_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)

    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
