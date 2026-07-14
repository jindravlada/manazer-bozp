from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment


class HazardRiskAssessmentRepository:
    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRiskAssessment]:
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem

        with get_session() as session:
            stmt = (
                select(HazardRiskAssessment)
                .join(HazardEvent, HazardRiskAssessment.hazard_event_id == HazardEvent.id)
                .join(
                    HazardInventoryItem,
                    HazardEvent.inventory_item_id == HazardInventoryItem.id,
                )
                .where(
                    HazardInventoryItem.hazard_identification_id == hazard_identification_id
                )
            )
            if not include_inactive:
                stmt = stmt.where(HazardRiskAssessment.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardRiskAssessment.hazard_event_id,
                HazardRiskAssessment.exposed_group,
                HazardRiskAssessment.id,
            )
            return list(session.scalars(stmt))

    def get_for_event(
        self,
        hazard_event_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRiskAssessment]:
        with get_session() as session:
            stmt = select(HazardRiskAssessment).where(
                HazardRiskAssessment.hazard_event_id == hazard_event_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardRiskAssessment.active == True)  # noqa: E712
            stmt = stmt.order_by(HazardRiskAssessment.exposed_group, HazardRiskAssessment.id)
            return list(session.scalars(stmt))

    def get_by_id(self, assessment_id: int) -> HazardRiskAssessment | None:
        with get_session() as session:
            return session.get(HazardRiskAssessment, assessment_id)

    def add(self, assessment: HazardRiskAssessment) -> HazardRiskAssessment:
        with get_session() as session:
            session.add(assessment)
            session.commit()
            session.refresh(assessment)
            return assessment

    def update(self, assessment: HazardRiskAssessment) -> HazardRiskAssessment:
        with get_session() as session:
            assessment = session.merge(assessment)
            session.commit()
            session.refresh(assessment)
            return assessment

    def count_active_for_event(self, hazard_event_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardRiskAssessment)
                .where(
                    HazardRiskAssessment.hazard_event_id == hazard_event_id,
                    HazardRiskAssessment.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)
