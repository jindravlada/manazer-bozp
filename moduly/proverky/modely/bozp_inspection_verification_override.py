from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class BozpInspectionVerificationOverride(Base):
    """Výjimka typu ověření kontrolního bodu pro konkrétní prověrku."""

    __tablename__ = "bozp_inspection_verification_overrides"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            "source_area_id",
            "source_section_id",
            "source_control_point_id",
            name="uq_bozp_inspection_verification_override",
        ),
        Index(
            "ix_bozp_inspection_verification_overrides_inspection_id",
            "inspection_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(Integer, nullable=False)

    source_area_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_section_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_control_point_id: Mapped[str] = mapped_column(
        String(80), default="", nullable=False
    )
    override_verification_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
