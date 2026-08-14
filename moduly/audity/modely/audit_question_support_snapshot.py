"""Zmrazená metodická podpora jedné snapshotové otázky (AUDIT-METHOD-SUPPORT-SNAPSHOT-1)."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditQuestionSupportSnapshot(Base):
    """1:1 metodická podpora vázaná na řádek audit_question_snapshots."""

    __tablename__ = "audit_question_support_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "audit_question_snapshot_id",
            name="uq_audit_question_support_snapshot_qid",
        ),
        Index(
            "ix_audit_question_support_snapshots_audit_id",
            "audit_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    audit_question_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)

    payload_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    support_payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    source: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    integrity_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
