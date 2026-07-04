from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class BozpAnnualReport(Base):
    """Ručně doplňovaná část roční zprávy BOZP pro daný kalendářní rok."""

    __tablename__ = "bozp_annual_reports"
    __table_args__ = (UniqueConstraint("year", name="uq_bozp_annual_reports_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    silne_stranky: Mapped[str] = mapped_column(Text, default="", nullable=False)
    top_priority: Mapped[str] = mapped_column(Text, default="", nullable=False)
    doporuceni_specialisty: Mapped[str] = mapped_column(Text, default="", nullable=False)
    zpracoval: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    zpracoval_worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
