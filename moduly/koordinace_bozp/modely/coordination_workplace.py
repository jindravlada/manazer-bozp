"""Místo výkonu práce v rámci koordinace (COORD-006)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationWorkplace(Base):
    """Provoz / pracoviště / část, pro které koordinace platí."""

    __tablename__ = "coordination_workplaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("bozp_coordinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
