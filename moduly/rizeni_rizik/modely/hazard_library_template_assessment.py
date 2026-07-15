from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardLibraryTemplateAssessment(Base):
    __tablename__ = "hazard_library_template_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exposed_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    consequence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
