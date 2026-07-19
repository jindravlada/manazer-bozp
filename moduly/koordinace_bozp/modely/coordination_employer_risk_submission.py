"""Evidence předání rizik dodavatelem (COORD-006)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import RISK_SUBMISSION_METHOD_NOT_SUBMITTED


class CoordinationEmployerRiskSubmission(Base):
    """Způsob předání rizik konkrétního dodavatele hlavnímu zaměstnavateli."""

    __tablename__ = "coordination_employer_risk_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    submission_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RISK_SUBMISSION_METHOD_NOT_SUBMITTED,
    )
    submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_reference: Mapped[str] = mapped_column(String(300), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
