"""AUDIT-EXTRAORDINARY-1: evidence mimořádných otázek a cílových provozů."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.audity.constants import (
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
    EXTRAORDINARY_TARGET_STATUS_PENDING,
)


class AuditExtraordinaryQuestion(Base):
    __tablename__ = "audit_extraordinary_questions"
    __table_args__ = (
        Index("ix_audit_extraordinary_questions_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    assigned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default=EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
        nullable=False,
    )
    process_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    process_name: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )


class AuditExtraordinaryQuestionTarget(Base):
    __tablename__ = "audit_extraordinary_question_targets"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "workplace_id",
            name="uq_audit_extraordinary_question_target",
        ),
        Index("ix_audit_extraordinary_targets_question_id", "question_id"),
        Index("ix_audit_extraordinary_targets_workplace_id", "workplace_id"),
        Index("ix_audit_extraordinary_targets_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    workplace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        default=EXTRAORDINARY_TARGET_STATUS_PENDING,
        nullable=False,
    )
    assigned_audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
