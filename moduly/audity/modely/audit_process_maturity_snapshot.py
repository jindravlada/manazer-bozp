from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditProcessMaturitySnapshot(Base):
    """Roční snapshot vyspělosti řídicího procesu pro historii a trendy."""

    __tablename__ = "audit_process_maturity_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "audit_program_id",
            "process_id",
            name="uq_audit_process_maturity_year_program_process",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_program_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_id: Mapped[str] = mapped_column(String(80), nullable=False)
    process_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    maturity_level: Mapped[str] = mapped_column(String(30), nullable=False)
    maturity_emoji: Mapped[str] = mapped_column(String(8), default="", nullable=False)
    maturity_label: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    weighted_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audits_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    control_points_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nevyhovuje_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    doporuceni_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_measures_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overdue_measures_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    trend_label: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", insert_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
