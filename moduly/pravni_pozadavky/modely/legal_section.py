from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalSection(Base):
    """Část struktury právního předpisu."""

    __tablename__ = "legal_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_document_version_id: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_section_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    section_type: Mapped[str] = mapped_column(String(30), nullable=False)
    section_number: Mapped[str] = mapped_column(String(50), default="")
    paragraph: Mapped[str] = mapped_column(String(50), default="")
    item_letter: Mapped[str] = mapped_column(String(20), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
