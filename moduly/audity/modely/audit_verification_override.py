from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class AuditVerificationOverride(Base):
    """Výjimka typu ověření auditního tvrzení pro konkrétní audit."""

    __tablename__ = "audit_verification_overrides"
    __table_args__ = (
        UniqueConstraint(
            "audit_id",
            "source_area_id",
            "source_section_id",
            "source_control_point_id",
            name="uq_audit_verification_override",
        ),
        Index(
            "ix_audit_verification_overrides_audit_id",
            "audit_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # process_id / criterion_id / assertion_id (stejný klíčový vzor jako u Prověrek)
    source_area_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_section_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_control_point_id: Mapped[str] = mapped_column(
        String(80), default="", nullable=False
    )
    override_verification_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
