"""Historická verze údajů / osvědčení OZO."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class OzoPersonPeriod(Base):
    __tablename__ = "ozo_person_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ozo_person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ozo_persons.id"),
        nullable=False,
        index=True,
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    title_before: Mapped[str] = mapped_column(String(50), default="")
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    title_after: Mapped[str] = mapped_column(String(50), default="")
    residence_address: Mapped[str] = mapped_column(String(300), default="")

    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(100), default="")
    certificate_valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
