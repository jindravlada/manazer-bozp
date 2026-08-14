"""Snapshot sady auditních tvrzení pro jeden audit (AUDIT-SNAPSHOT-0).

Tabulka je připravena aditivně. V této fázi se neplní automaticky.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditQuestionSnapshot(Base):
    """Jedno zmrazené auditní tvrzení vázané na konkrétní audit."""

    __tablename__ = "audit_question_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "audit_id",
            "process_id",
            "section_id",
            "assertion_id",
            name="uq_audit_question_snapshot_key",
        ),
        Index("ix_audit_question_snapshots_audit_id", "audit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    process_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    process_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    section_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    section_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    assertion_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    assertion_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    verification_type: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    question_kind: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
