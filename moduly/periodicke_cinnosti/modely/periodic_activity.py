"""Definice periodické činnosti."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.periodicke_cinnosti.constants import (
    DEFAULT_NEXT_FROM,
    DEFAULT_NOTIFY_EVERY,
    DEFAULT_NOTIFY_UNIT,
    DEFAULT_PLACE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
)


class PeriodicActivity(Base):
    __tablename__ = "periodic_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    place_kind: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_PLACE_KIND,
        nullable=False,
    )
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(150), default="")
    place_text: Mapped[str] = mapped_column(String(200), default="")

    responsible_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_person_name: Mapped[str] = mapped_column(String(150), default="")

    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    repeat_every: Mapped[int] = mapped_column(Integer, default=DEFAULT_REPEAT_EVERY, nullable=False)
    repeat_unit: Mapped[str] = mapped_column(String(20), default=DEFAULT_REPEAT_UNIT, nullable=False)

    notify_every: Mapped[int] = mapped_column(Integer, default=DEFAULT_NOTIFY_EVERY, nullable=False)
    notify_unit: Mapped[str] = mapped_column(String(20), default=DEFAULT_NOTIFY_UNIT, nullable=False)

    next_from: Mapped[str] = mapped_column(String(20), default=DEFAULT_NEXT_FROM, nullable=False)

    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
