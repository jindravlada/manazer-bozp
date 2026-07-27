from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.constants import RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED


class RiskMeasureReviewItem(Base):
    """Položka checklistu přezkoumání – vazba na navazující opatření (RISK-REVIEW-1)."""

    __tablename__ = "risk_measure_review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    follow_up_measure_id: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
