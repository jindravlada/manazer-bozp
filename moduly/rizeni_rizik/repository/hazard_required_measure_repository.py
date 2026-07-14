from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure


class HazardRequiredMeasureRepository:
    def get_for_assessment(
        self,
        hazard_risk_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRequiredMeasure]:
        with get_session() as session:
            stmt = select(HazardRequiredMeasure).where(
                HazardRequiredMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardRequiredMeasure.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardRequiredMeasure.sort_order,
                HazardRequiredMeasure.description,
                HazardRequiredMeasure.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, measure_id: int) -> HazardRequiredMeasure | None:
        with get_session() as session:
            return session.get(HazardRequiredMeasure, measure_id)

    def add(self, measure: HazardRequiredMeasure) -> HazardRequiredMeasure:
        with get_session() as session:
            session.add(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def update(self, measure: HazardRequiredMeasure) -> HazardRequiredMeasure:
        with get_session() as session:
            measure = session.merge(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def count_active_for_assessment(self, hazard_risk_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardRequiredMeasure)
                .where(
                    HazardRequiredMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id,
                    HazardRequiredMeasure.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, hazard_risk_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardRequiredMeasure.sort_order)
                .where(HazardRequiredMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id)
                .order_by(HazardRequiredMeasure.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
