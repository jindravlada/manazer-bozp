"""Evidence zpracování měsíce Ročního plánu."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class YearlyPlanMonthStatus(Base):
    __tablename__ = "yearly_plan_month_status"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_yearly_plan_month_status_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )
