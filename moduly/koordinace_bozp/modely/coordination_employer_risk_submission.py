"""Evidence předání rizik dodavatelem (COORD-006 / UX-COORD-13)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.koordinace_bozp.constants import (
    RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
)


class CoordinationEmployerRiskSubmission(Base):
    """Stav předání rizik konkrétního dodavatele hlavnímu zaměstnavateli."""

    __tablename__ = "coordination_employer_risk_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Sloupec submission_method drží kód stavu předání (UX-COORD-13).
    submission_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
    )
    submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_reference: Mapped[str] = mapped_column(String(300), default="")
    expected_email: Mapped[str] = mapped_column(String(150), default="")
    risks_text: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class CoordinationRiskSubmissionHistory(Base):
    """Historie změn stavu předání rizik (UX-COORD-13)."""

    __tablename__ = "coordination_risk_submission_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employer_risk_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    to_status: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_reference: Mapped[str] = mapped_column(String(300), default="")
    expected_email: Mapped[str] = mapped_column(String(150), default="")
    risks_text: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
