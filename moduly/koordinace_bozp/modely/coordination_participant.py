"""Účastník koordinační schůzky (COORD-003)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import COORDINATION_PARTICIPANT_SOURCE_MANUAL


class CoordinationParticipant(Base):
    """Osoba jednající za konkrétního zúčastněného zaměstnavatele."""

    __tablename__ = "coordination_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=COORDINATION_PARTICIPANT_SOURCE_MANUAL,
    )
    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    full_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(150), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
