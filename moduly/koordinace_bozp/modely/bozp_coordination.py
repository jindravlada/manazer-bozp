"""Entita koordinační schůzky BOZP (COORD-001)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import DEFAULT_BOZP_COORDINATION_STATUS


class BozpCoordination(Base):
    """Základní evidence jedné koordinace BOZP."""

    __tablename__ = "bozp_coordinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    place: Mapped[str] = mapped_column(String(300), default="")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_BOZP_COORDINATION_STATUS,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
