"""Evidence smlouvy OZO."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.smlouvy_ozo.constants import (
    DEFAULT_NOTIFY_BEFORE_UNIT,
    DEFAULT_NOTIFY_BEFORE_VALUE,
)


class OzoContract(Base):
    __tablename__ = "ozo_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    employer_name: Mapped[str] = mapped_column(String(250), nullable=False)
    ico: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(String(300), default="")

    contact_person: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")

    contract_number: Mapped[str] = mapped_column(String(100), default="")
    signed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    indefinite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    notify_before_value: Mapped[int] = mapped_column(
        Integer,
        default=DEFAULT_NOTIFY_BEFORE_VALUE,
        nullable=False,
    )
    notify_before_unit: Mapped[str] = mapped_column(
        String(20),
        default=DEFAULT_NOTIFY_BEFORE_UNIT,
        nullable=False,
    )

    services_scope: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
