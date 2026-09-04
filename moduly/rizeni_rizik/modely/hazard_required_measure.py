from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardRequiredMeasure(Base):
    __tablename__ = "hazard_required_measures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_risk_assessment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    modified: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )

    def display_title(self) -> str:
        """Znění kontrolní otázky (title, zpětně kompatibilní s description)."""
        return (self.title or self.description or "").strip()

    def display_description(self) -> str:
        """Volitelný popis (note; případně description odlišný od title)."""
        title = (self.title or "").strip()
        description = (self.description or "").strip()
        note = (self.note or "").strip()
        if note and note != title:
            return note
        if title and description and description != title:
            return description
        if not title:
            return note
        return ""
