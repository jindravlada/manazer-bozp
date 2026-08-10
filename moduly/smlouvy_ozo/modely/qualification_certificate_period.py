"""Historická verze ostatního osvědčení."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.smlouvy_ozo.constants import UNIT_DAYS


class QualificationCertificatePeriod(Base):
    __tablename__ = "qualification_certificate_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    certificate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("qualification_certificates.id"),
        nullable=False,
        index=True,
    )

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to_period: Mapped[date | None] = mapped_column(Date, nullable=True)

    certificate_number: Mapped[str] = mapped_column(String(100), default="")
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    indefinite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    certificate_valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    notify_before_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notify_before_unit: Mapped[str] = mapped_column(
        String(20),
        default=UNIT_DAYS,
        nullable=False,
    )

    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
