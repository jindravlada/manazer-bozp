from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalRequirementCheck(Base):
    """Záznam ověření plnění právního požadavku."""

    __tablename__ = "legal_requirement_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_requirement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("legal_requirements.id"),
        nullable=False,
    )

    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[str] = mapped_column(String(50), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    next_check_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
