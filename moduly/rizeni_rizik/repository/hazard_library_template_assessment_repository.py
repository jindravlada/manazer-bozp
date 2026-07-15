from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)


class HazardLibraryTemplateAssessmentRepository:
    def get_for_event(
        self,
        template_event_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateAssessment]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateAssessment).where(
                HazardLibraryTemplateAssessment.template_event_id == template_event_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateAssessment.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateAssessment.sort_order,
                HazardLibraryTemplateAssessment.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, assessment_id: int) -> HazardLibraryTemplateAssessment | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateAssessment, assessment_id)

    def add(
        self,
        assessment: HazardLibraryTemplateAssessment,
    ) -> HazardLibraryTemplateAssessment:
        with get_session() as session:
            session.add(assessment)
            session.commit()
            session.refresh(assessment)
            return assessment

    def update(
        self,
        assessment: HazardLibraryTemplateAssessment,
    ) -> HazardLibraryTemplateAssessment:
        with get_session() as session:
            assessment = session.merge(assessment)
            session.commit()
            session.refresh(assessment)
            return assessment

    def count_active_for_event(self, template_event_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(func.count())
                .select_from(HazardLibraryTemplateAssessment)
                .where(
                    HazardLibraryTemplateAssessment.template_event_id == template_event_id,
                    HazardLibraryTemplateAssessment.active == True,  # noqa: E712
                )
            )
            return int(session.scalar(stmt) or 0)

    def next_sort_order(self, template_event_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateAssessment.sort_order)
                .where(
                    HazardLibraryTemplateAssessment.template_event_id == template_event_id
                )
                .order_by(HazardLibraryTemplateAssessment.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
