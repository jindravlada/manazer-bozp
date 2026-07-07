from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalChange(Base):
    """Ručně evidovaná změna legislativy."""

    __tablename__ = "legal_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_document_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_check_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    evaluated: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evaluated_by: Mapped[str] = mapped_column(String(150), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
