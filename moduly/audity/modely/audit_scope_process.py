"""Rozsah ručního auditu: vybrané řídicí procesy před snapshotem."""

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditScopeProcess(Base):
    __tablename__ = "audit_scope_processes"
    __table_args__ = (
        UniqueConstraint(
            "audit_id",
            "process_id",
            name="uq_audit_scope_processes_audit_process",
        ),
        Index("ix_audit_scope_processes_audit_id", "audit_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    process_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    process_name: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
