from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.constants import RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT


class RiskMeasureReviewItem(Base):
    """Položka checklistu přezkoumání – vazba na navazující opatření."""

    __tablename__ = "risk_measure_review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    follow_up_measure_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # RISK-REVIEW-2a: jedno zaškrtávací „Vyhovuje“ (False = zjištěn problém).
    compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Krátký odkaz na společný seznam poznámek (např. „1“, „2“).
    note_number: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # Příznak, že k položce byla pořízena fotografie (samotné foto v další fázi).
    has_photo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Zpětná kompatibilita s RISK-REVIEW-2 (sync z compliant).
    result: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    )
    note: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
