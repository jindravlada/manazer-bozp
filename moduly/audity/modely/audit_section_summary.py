"""Souhrnné sdělení za okruh auditu (AUDIT-PROVERKY-SECTION-NOTE-1)."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditSectionSummary(Base):
    __tablename__ = "audit_section_summaries"
    __table_args__ = (
        UniqueConstraint(
            "audit_id",
            "process_id",
            "section_id",
            name="uq_audit_section_summaries_key",
        ),
        Index("ix_audit_section_summaries_audit_id", "audit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    process_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    section_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
