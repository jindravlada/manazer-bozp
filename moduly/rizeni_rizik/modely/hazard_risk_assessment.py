from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardRiskAssessment(Base):
    __tablename__ = "hazard_risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hazard_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exposed_group: Mapped[str] = mapped_column(String(200), nullable=False)
    consequence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    assessment_status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    conclusion: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
    )
