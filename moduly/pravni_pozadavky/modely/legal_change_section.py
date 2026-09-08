from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class LegalChangeSection(Base):
    """Změněné ustanovení navázané na zjištěnou změnu legislativy."""

    __tablename__ = "legal_change_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legal_change_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("legal_changes.id"),
        nullable=False,
    )
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    section_label: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    old_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
