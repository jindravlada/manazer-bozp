"""Údaje odborně způsobilé osoby (singleton pro výstupy § 10)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class OzoPerson(Base):
    __tablename__ = "ozo_persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
