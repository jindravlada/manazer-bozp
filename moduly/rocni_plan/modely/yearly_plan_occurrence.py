"""Výjimka / realizace konkrétního výskytu opakované položky Ročního plánu."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rocni_plan.constants import DEFAULT_STATUS


class YearlyPlanOccurrence(Base):
    """
    Evidence jednoho výskytu opakované definice.

    Klíč: definition_id + year + month (původní slot v řadě).
    display_year / display_month: kam se výskyt aktuálně zobrazuje (po přesunu).
    """

    __tablename__ = "yearly_plan_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "year",
            "month",
            name="uq_yearly_plan_occurrence_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    definition_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    display_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    display_month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), default=DEFAULT_STATUS, nullable=False)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
