from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
    HazardLibraryTemplateAssessmentExposedGroup,
)


class HazardLibraryTemplateAssessmentExposedGroupRepository:
    def list_group_ids(self, assessment_id: int) -> list[int]:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateAssessmentExposedGroup.exposed_group_id)
                .where(
                    HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                    == assessment_id,
                )
                .order_by(
                    HazardLibraryTemplateAssessmentExposedGroup.sort_order,
                    HazardLibraryTemplateAssessmentExposedGroup.id,
                )
            )
            return [int(value) for value in session.scalars(stmt)]

    def replace_groups(self, assessment_id: int, group_ids: list[int]) -> None:
        unique_ids: list[int] = []
        seen: set[int] = set()
        for group_id in group_ids:
            if group_id in seen:
                continue
            seen.add(group_id)
            unique_ids.append(int(group_id))

        with get_session() as session:
            session.execute(
                delete(HazardLibraryTemplateAssessmentExposedGroup).where(
                    HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                    == assessment_id,
                ),
            )
            for sort_order, group_id in enumerate(unique_ids, start=1):
                session.add(
                    HazardLibraryTemplateAssessmentExposedGroup(
                        assessment_id=assessment_id,
                        exposed_group_id=group_id,
                        sort_order=sort_order,
                    ),
                )
            session.commit()

    def list_assessment_ids_for_groups(
        self,
        group_ids: list[int],
        *,
        exclude_assessment_id: int | None = None,
    ) -> list[int]:
        if not group_ids:
            return []
        with get_session() as session:
            stmt = select(
                HazardLibraryTemplateAssessmentExposedGroup.assessment_id,
            ).where(
                HazardLibraryTemplateAssessmentExposedGroup.exposed_group_id.in_(
                    group_ids,
                ),
            )
            if exclude_assessment_id is not None:
                stmt = stmt.where(
                    HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                    != exclude_assessment_id,
                )
            return list({int(value) for value in session.scalars(stmt)})
