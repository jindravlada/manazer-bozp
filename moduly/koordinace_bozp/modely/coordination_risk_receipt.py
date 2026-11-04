"""Následné převzetí rizik dodavatele (fáze B).

Samostatný záznam. Nemění dohodu v ``coordination_employer_risk_submissions``,
ze které se sestavuje koordinační protokol.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class CoordinationRiskReceipt(Base):
    """Skutečné převzetí informací o rizicích jednoho dodavatele."""

    __tablename__ = "coordination_risk_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coordination_employer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_employers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    receipt_method: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_location: Mapped[str] = mapped_column(String(300), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    attachment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Okamžik prvního zaevidování. Opravy aktuálních údajů ho nemění.
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class CoordinationRiskReceiptHistory(Base):
    """Oprava následného převzetí: původní i nové hodnoty a okamžik změny."""

    __tablename__ = "coordination_risk_receipt_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coordination_risk_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    received_on_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    received_on_after: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_method_before: Mapped[str] = mapped_column(String(32), default="")
    receipt_method_after: Mapped[str] = mapped_column(String(32), default="")
    storage_location_before: Mapped[str] = mapped_column(String(300), default="")
    storage_location_after: Mapped[str] = mapped_column(String(300), default="")
    note_before: Mapped[str] = mapped_column(Text, default="")
    note_after: Mapped[str] = mapped_column(Text, default="")
    attachment_id_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attachment_id_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
