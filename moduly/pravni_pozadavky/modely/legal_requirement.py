from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.pravni_pozadavky.constants import DEFAULT_PROCESSING_STATUS


class LegalRequirement(Base):
    """Evidence právního požadavku a jeho plnění."""

    __tablename__ = "legal_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(250), default="")
    regulation_name: Mapped[str] = mapped_column(String(250), default="")
    regulation_number: Mapped[str] = mapped_column(String(100), default="")
    provision: Mapped[str] = mapped_column(String(200), default="")
    area: Mapped[str] = mapped_column(String(150), default="")

    legal_document_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    requirement_summary: Mapped[str] = mapped_column(Text, default="")
    organization_impact: Mapped[str] = mapped_column(Text, default="")

    responsible_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_person_name: Mapped[str] = mapped_column(String(150), default="")
    responsible_role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    responsible_role_name: Mapped[str] = mapped_column(String(150), default="")

    verification_periodicity: Mapped[str] = mapped_column(String(50), default="")
    last_verification_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_verification_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    compliance_status: Mapped[str] = mapped_column(String(50), default="")
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default=DEFAULT_PROCESSING_STATUS,
    )
    note: Mapped[str] = mapped_column(Text, default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
