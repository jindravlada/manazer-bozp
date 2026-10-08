from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class FindingStatusEvent(Base):
    """Trvalý záznam jedné skutečné změny stavu sdíleného zjištění.

    Řádek se po vložení nemění. Úprava textu zjištění ani opakovaný start
    aplikace ho nepřepisuje. Datum vypořádání před změnou a po ní zůstává
    v tomto řádku i poté, co se aktuální ``findings.resolved_at`` změní.
    """

    __tablename__ = "finding_status_events"
    __table_args__ = (
        Index("ix_finding_status_events_finding_id", "finding_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(Integer, nullable=False)
    old_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    origin: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    resolved_at_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_at_after: Mapped[date | None] = mapped_column(Date, nullable=True)
