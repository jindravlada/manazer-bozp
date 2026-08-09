"""Historie přesunu položky Ročního plánu."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class YearlyPlanItemMove(Base):
    __tablename__ = "yearly_plan_item_moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    from_year: Mapped[int] = mapped_column(Integer, nullable=False)
    from_month: Mapped[int] = mapped_column(Integer, nullable=False)
    to_year: Mapped[int] = mapped_column(Integer, nullable=False)
    to_month: Mapped[int] = mapped_column(Integer, nullable=False)

    moved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
