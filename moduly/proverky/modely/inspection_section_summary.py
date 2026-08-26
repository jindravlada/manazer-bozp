"""Souhrnné sdělení za okruh prověrky (AUDIT-PROVERKY-SECTION-NOTE-1)."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class InspectionSectionSummary(Base):
    __tablename__ = "inspection_section_summaries"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            "area_id",
            "section_id",
            name="uq_inspection_section_summaries_key",
        ),
        Index("ix_inspection_section_summaries_inspection_id", "inspection_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    area_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    section_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
