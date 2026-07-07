from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalRequirementSource(Base):
    """Právní podklad procesního požadavku."""

    __tablename__ = "legal_requirement_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("legal_requirements.id"),
        nullable=False,
    )
    legal_section_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
