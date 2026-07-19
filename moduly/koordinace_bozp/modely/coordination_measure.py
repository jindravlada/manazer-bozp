"""Organizační opatření koordinace (COORD-009)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import DEFAULT_MEASURE_CATEGORY


class CoordinationMeasure(Base):
    """Organizační opatření společné pro celou koordinaci."""

    __tablename__ = "coordination_measures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_MEASURE_CATEGORY,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
