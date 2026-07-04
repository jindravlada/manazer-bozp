from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditProgramFinalReport(Base):
    """Ručně doplňovaná část závěrečné zprávy programu interních auditů."""

    __tablename__ = "audit_program_final_reports"
    __table_args__ = (
        UniqueConstraint(
            "audit_program_id",
            name="uq_audit_program_final_reports_program",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_program_id: Mapped[int] = mapped_column(Integer, nullable=False)
    silne_stranky: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hlavni_slabiny: Mapped[str] = mapped_column(Text, default="", nullable=False)
    doporuceni_novy_program: Mapped[str] = mapped_column(Text, default="", nullable=False)
    zpracoval: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    zpracoval_worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
