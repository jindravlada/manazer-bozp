from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.constants import RISK_MEASURE_REVIEW_STATUS_DRAFT


class RiskMeasureReview(Base):
    """Hlavička přezkoumání opatření rizik (RISK-REVIEW-1)."""

    __tablename__ = "risk_measure_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_number: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    reviewer_person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_person_name: Mapped[str] = mapped_column(String(250), nullable=False, default="")
    operation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    workplace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    workplace_part_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workplace_part_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RISK_MEASURE_REVIEW_STATUS_DRAFT,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
