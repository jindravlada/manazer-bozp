"""Entita koordinační schůzky BOZP (COORD-001 / UX-COORD-6a)."""

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
    emergency_reporting: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    accident_reporting: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    fire_reporting: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    evacuation_instructions: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    work_intent_information_text: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    ppe_text: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    workplace_handover_text: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    final_provisions_text: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="",
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
