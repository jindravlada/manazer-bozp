from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
    HazardLibraryTemplateAssessmentExposedGroup,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SOURCE_TYPE_HAZARD_GROUP,
    ExposedTargetRef,
    refs_from_legacy_group_ids,
)


class HazardLibraryTemplateAssessmentExposedGroupRepository:
    def list_refs(self, assessment_id: int) -> list[ExposedTargetRef]:
        with get_session() as session:
            stmt = (
                select(
                    HazardLibraryTemplateAssessmentExposedGroup.source_type,
                    HazardLibraryTemplateAssessmentExposedGroup.exposed_group_id,
                )
                .where(
                    HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                    == assessment_id,
                )
                .order_by(
                    HazardLibraryTemplateAssessmentExposedGroup.sort_order,
                    HazardLibraryTemplateAssessmentExposedGroup.id,
                )
            )
            refs: list[ExposedTargetRef] = []
            for source_type, source_id in session.execute(stmt):
                refs.append(
                    ExposedTargetRef(
                        str(source_type or SOURCE_TYPE_HAZARD_GROUP),
                        int(source_id),
                    )
                )
            return refs

    def list_group_ids(self, assessment_id: int) -> list[int]:
        return [
            ref.source_id
            for ref in self.list_refs(assessment_id)
            if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]

    def replace_refs(
        self,
        assessment_id: int,
        refs: list[ExposedTargetRef],
    ) -> None:
        unique: list[ExposedTargetRef] = []
        seen: set[tuple[str, int]] = set()
        for ref in refs:
            if ref.key in seen:
                continue
            seen.add(ref.key)
            unique.append(ref)

        with get_session() as session:
            session.execute(
                delete(HazardLibraryTemplateAssessmentExposedGroup).where(
                    HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                    == assessment_id,
                ),
            )
            for sort_order, ref in enumerate(unique, start=1):
                session.add(
                    HazardLibraryTemplateAssessmentExposedGroup(
                        assessment_id=assessment_id,
                        exposed_group_id=ref.source_id,
                        source_type=ref.source_type,
                        sort_order=sort_order,
                    ),
                )
            session.commit()

    def replace_groups(self, assessment_id: int, group_ids: list[int]) -> None:
        self.replace_refs(assessment_id, refs_from_legacy_group_ids(group_ids))

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
                HazardLibraryTemplateAssessmentExposedGroup.source_type
                == SOURCE_TYPE_HAZARD_GROUP,
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
