"""Činnost zúčastněného zaměstnavatele v rámci koordinace (COORD-008)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationEmployerActivity(Base):
    """Činnost konkrétního zaměstnavatele na místě koordinace."""

    __tablename__ = "coordination_employer_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coordination_workplace_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("coordination_workplaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    activity_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    planned_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
