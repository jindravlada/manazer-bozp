from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure


class HazardExistingMeasureRepository:
    def get_for_assessment(
        self,
        hazard_risk_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardExistingMeasure]:
        with get_session() as session:
            stmt = select(HazardExistingMeasure).where(
                HazardExistingMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardExistingMeasure.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardExistingMeasure.sort_order,
                HazardExistingMeasure.description,
                HazardExistingMeasure.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, measure_id: int) -> HazardExistingMeasure | None:
        with get_session() as session:
            return session.get(HazardExistingMeasure, measure_id)

    def add(self, measure: HazardExistingMeasure) -> HazardExistingMeasure:
        with get_session() as session:
            session.add(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def update(self, measure: HazardExistingMeasure) -> HazardExistingMeasure:
        with get_session() as session:
            measure = session.merge(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def count_active_for_assessment(self, hazard_risk_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardExistingMeasure)
                .where(
                    HazardExistingMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id,
                    HazardExistingMeasure.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, hazard_risk_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardExistingMeasure.sort_order)
                .where(HazardExistingMeasure.hazard_risk_assessment_id == hazard_risk_assessment_id)
                .order_by(HazardExistingMeasure.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
