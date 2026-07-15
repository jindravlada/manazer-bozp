from sqlalchemy import func, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateExistingMeasure,
    HazardLibraryTemplateRequiredMeasure,
)


class HazardLibraryTemplateExistingMeasureRepository:
    def get_for_assessment(
        self,
        template_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateExistingMeasure]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateExistingMeasure).where(
                HazardLibraryTemplateExistingMeasure.template_assessment_id
                == template_assessment_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateExistingMeasure.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateExistingMeasure.sort_order,
                HazardLibraryTemplateExistingMeasure.description,
                HazardLibraryTemplateExistingMeasure.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, measure_id: int) -> HazardLibraryTemplateExistingMeasure | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateExistingMeasure, measure_id)

    def add(
        self,
        measure: HazardLibraryTemplateExistingMeasure,
    ) -> HazardLibraryTemplateExistingMeasure:
        with get_session() as session:
            session.add(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def update(
        self,
        measure: HazardLibraryTemplateExistingMeasure,
    ) -> HazardLibraryTemplateExistingMeasure:
        with get_session() as session:
            measure = session.merge(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def next_sort_order(self, template_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateExistingMeasure.sort_order)
                .where(
                    HazardLibraryTemplateExistingMeasure.template_assessment_id
                    == template_assessment_id
                )
                .order_by(HazardLibraryTemplateExistingMeasure.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1


class HazardLibraryTemplateRequiredMeasureRepository:
    def get_for_assessment(
        self,
        template_assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateRequiredMeasure]:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateRequiredMeasure).where(
                HazardLibraryTemplateRequiredMeasure.template_assessment_id
                == template_assessment_id
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplateRequiredMeasure.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplateRequiredMeasure.sort_order,
                HazardLibraryTemplateRequiredMeasure.description,
                HazardLibraryTemplateRequiredMeasure.id,
            )
            return list(session.scalars(stmt))

    def get_by_id(self, measure_id: int) -> HazardLibraryTemplateRequiredMeasure | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplateRequiredMeasure, measure_id)

    def add(
        self,
        measure: HazardLibraryTemplateRequiredMeasure,
    ) -> HazardLibraryTemplateRequiredMeasure:
        with get_session() as session:
            session.add(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def update(
        self,
        measure: HazardLibraryTemplateRequiredMeasure,
    ) -> HazardLibraryTemplateRequiredMeasure:
        with get_session() as session:
            measure = session.merge(measure)
            session.commit()
            session.refresh(measure)
            return measure

    def next_sort_order(self, template_assessment_id: int) -> int:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateRequiredMeasure.sort_order)
                .where(
                    HazardLibraryTemplateRequiredMeasure.template_assessment_id
                    == template_assessment_id
                )
                .order_by(HazardLibraryTemplateRequiredMeasure.sort_order.desc())
            )
            current = session.scalar(stmt)
            return int(current or 0) + 1
