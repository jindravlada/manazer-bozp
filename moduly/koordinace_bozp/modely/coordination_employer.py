"""Zúčastněný zaměstnavatel u koordinace BOZP (COORD-002)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import COORDINATION_EMPLOYER_TYPE_PARTICIPANT


class CoordinationEmployer(Base):
    """Zaměstnavatel zúčastněný na koordinační schůzce."""

    __tablename__ = "coordination_employers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employer_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
    )
    company_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    ico: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    abbreviation: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
