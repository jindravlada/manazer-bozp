"""Uživatelská schválení formulací při kontrole PBP (UX-PBP-VALIDATION-1a)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base

# Souhrnné validační pravidlo (aktuální detekce nevhodné formulace).
PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE = "unsuitable_employee_rule"


class PbpValidationApproval(Base):
    """Trvalá výjimka kontroly PBP pro konkrétní znění opatření."""

    __tablename__ = "pbp_validation_approvals"
    __table_args__ = (
        UniqueConstraint(
            "measure_id",
            "validation_rule_code",
            name="uq_pbp_validation_approval_measure_rule",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measure_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    validation_rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
