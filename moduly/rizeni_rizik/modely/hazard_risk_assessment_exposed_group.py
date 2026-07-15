from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class HazardRiskAssessmentExposedGroup(Base):
    """M:N vazba posouzení rizika (inventarizace) na ohrožené skupiny (R20c)."""

    __tablename__ = "hazard_risk_assessment_exposed_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exposed_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
