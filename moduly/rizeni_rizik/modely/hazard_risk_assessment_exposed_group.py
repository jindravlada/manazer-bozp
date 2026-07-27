from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.sluzby.exposed_target_ref import SOURCE_TYPE_HAZARD_GROUP


class HazardRiskAssessmentExposedGroup(Base):
    """M:N vazba posouzení na ohrožené skupiny / funkce-role (RISK-UX-6)."""

    __tablename__ = "hazard_risk_assessment_exposed_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Polymorfní ID (role.id nebo exposed_groups.id) podle source_type.
    exposed_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SOURCE_TYPE_HAZARD_GROUP,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def source_id(self) -> int:
        return int(self.exposed_group_id)
