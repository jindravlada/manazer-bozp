from dataclasses import dataclass
from datetime import datetime

from core.utils.czech_sort import czech_sorted
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.rizeni_rizik.constants import (
    RISK_SEVERITIES,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SOURCE_TYPE_HAZARD_GROUP,
    SOURCE_TYPE_ROLE,
    ExposedTargetRef,
    format_exposed_target_names,
    legacy_exposed_group_id,
    refs_from_legacy_group_ids,
    resolve_exposed_target_display_name,
)
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.repository.hazard_library_template_assessment_exposed_group_repository import (
    HazardLibraryTemplateAssessmentExposedGroupRepository,
)
from moduly.rizeni_rizik.repository.hazard_library_template_assessment_repository import (
    HazardLibraryTemplateAssessmentRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)


class HazardLibraryTemplateAssessmentError(ValueError):
    pass


@dataclass
class HazardLibraryTemplateAssessmentRow:
    assessment: HazardLibraryTemplateAssessment
    exposed_group_name: str
    severity_label: str
    exposed_group_ids: tuple[int, ...] = ()
    target_refs: tuple[ExposedTargetRef, ...] = ()


class HazardLibraryTemplateAssessmentService:
    def __init__(self):
        self.repository = HazardLibraryTemplateAssessmentRepository()
        self.group_repository = HazardLibraryTemplateAssessmentExposedGroupRepository()

    def get_target_refs(self, assessment_id: int) -> list[ExposedTargetRef]:
        return self.group_repository.list_refs(assessment_id)

    def get_group_ids(self, assessment_id: int) -> list[int]:
        return self.group_repository.list_group_ids(assessment_id)

    def get_exposed_group_display_name(
        self,
        assessment: HazardLibraryTemplateAssessment,
    ) -> str:
        refs = self.group_repository.list_refs(assessment.id)
        if not refs and assessment.exposed_group_id:
            refs = [ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, assessment.exposed_group_id)]
        names = format_exposed_target_names(refs)
        return names if names else "—"

    def get_for_event(
        self,
        template_event_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateAssessmentRow]:
        assessments = self.repository.get_for_event(
            template_event_id,
            include_inactive=include_inactive,
        )
        rows = [self._to_row(assessment) for assessment in assessments]
        return self._sort_rows(rows)

    def get_by_id(self, assessment_id: int | None) -> HazardLibraryTemplateAssessment | None:
        if not assessment_id:
            return None
        return self.repository.get_by_id(assessment_id)

    def count_active_for_event(self, template_event_id: int) -> int:
        return self.repository.count_active_for_event(template_event_id)

    def count_active_by_events(self, template_id: int) -> dict[int, int]:
        counts: dict[int, int] = {}
        for event in hazard_library_template_event_service.get_for_template(
            template_id,
            include_inactive=True,
        ):
            counts[event.id] = self.repository.count_active_for_event(event.id)
        return counts

    def create_assessment(
        self,
        *,
        template_id: int,
        template_event_id: int,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        conclusion: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateAssessment:
        validated_refs = self._validate_target_refs(
            target_refs,
            exposed_group_ids=exposed_group_ids,
            legacy_single_id=exposed_group_id,
        )
        normalized_severity = self._validate_severity(severity)

        self._validate_event(template_id, template_event_id)
        self._validate_unique_active_refs(
            template_event_id,
            target_refs=validated_refs,
            exclude_assessment_id=None,
            active=active,
        )

        assessment = HazardLibraryTemplateAssessment(
            template_event_id=template_event_id,
            exposed_group_id=legacy_exposed_group_id(validated_refs),
            severity=normalized_severity,
            conclusion=conclusion.strip(),
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_event_id),
        )
        saved = self.repository.add(assessment)
        self.group_repository.replace_refs(saved.id, validated_refs)
        return saved

    def update_assessment(
        self,
        assessment_id: int,
        *,
        template_id: int,
        template_event_id: int,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        conclusion: str = "",
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateAssessment | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None

        old_refs = self.group_repository.list_refs(assessment_id)
        if not old_refs and assessment.exposed_group_id:
            old_refs = [ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, assessment.exposed_group_id)]
        validated_refs = self._validate_target_refs(
            target_refs,
            exposed_group_ids=exposed_group_ids,
            legacy_single_id=exposed_group_id,
        )
        normalized_severity = self._validate_severity(severity)

        self._validate_event(template_id, template_event_id)
        self._validate_unique_active_refs(
            template_event_id,
            target_refs=validated_refs,
            exclude_assessment_id=assessment_id,
            active=active,
        )

        assessment.template_event_id = template_event_id
        assessment.exposed_group_id = legacy_exposed_group_id(validated_refs)
        assessment.severity = normalized_severity
        assessment.conclusion = conclusion.strip()
        assessment.note = note.strip()
        assessment.active = active
        assessment.updated_at = datetime.now()
        saved = self.repository.update(assessment)
        if old_refs != validated_refs:
            from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
                hazard_library_template_existing_measure_service,
            )

            hazard_library_template_existing_measure_service.sync_relevance_for_assessment(
                saved.id,
                old_refs=old_refs,
                new_refs=validated_refs,
            )
        self.group_repository.replace_refs(saved.id, validated_refs)
        return saved

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        refs = self.group_repository.list_refs(assessment_id)
        if not refs and assessment.exposed_group_id:
            refs = [ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, assessment.exposed_group_id)]
        self._validate_unique_active_refs(
            assessment.template_event_id,
            target_refs=refs,
            exclude_assessment_id=assessment_id,
            active=True,
        )
        assessment.active = True
        assessment.updated_at = datetime.now()
        self.repository.update(assessment)
        return True

    def deactivate_assessment(self, assessment_id: int) -> bool:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return False
        assessment.active = False
        assessment.updated_at = datetime.now()
        self.repository.update(assessment)
        return True

    def get_template_id_for_assessment(self, assessment_id: int) -> int | None:
        assessment = self.repository.get_by_id(assessment_id)
        if assessment is None:
            return None
        return self._template_id_for_assessment(assessment)

    def _template_id_for_assessment(self, assessment: HazardLibraryTemplateAssessment) -> int:
        template_id = hazard_library_template_event_service.get_template_id_for_event(
            assessment.template_event_id
        )
        if template_id is None:
            raise HazardLibraryTemplateAssessmentError("Nežádoucí událost zdroje rizika neexistuje.")
        return template_id

    def _to_row(self, assessment: HazardLibraryTemplateAssessment) -> HazardLibraryTemplateAssessmentRow:
        refs = tuple(self.group_repository.list_refs(assessment.id))
        if not refs and assessment.exposed_group_id:
            refs = (ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, assessment.exposed_group_id),)
        group_ids = tuple(
            ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        )
        return HazardLibraryTemplateAssessmentRow(
            assessment=assessment,
            exposed_group_name=self.get_exposed_group_display_name(assessment),
            severity_label=format_risk_severity_label(assessment.severity),
            exposed_group_ids=group_ids,
            target_refs=refs,
        )

    def _sort_rows(
        self,
        rows: list[HazardLibraryTemplateAssessmentRow],
    ) -> list[HazardLibraryTemplateAssessmentRow]:
        return czech_sorted(rows, key=lambda row: row.exposed_group_name.casefold())

    def _validate_target_refs(
        self,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
        *,
        exposed_group_ids: list[int] | tuple[int, ...] | None,
        legacy_single_id: int | None,
    ) -> list[ExposedTargetRef]:
        if target_refs:
            values = list(target_refs)
        else:
            values = refs_from_legacy_group_ids(
                exposed_group_ids,
                legacy_single_id=legacy_single_id,
            )
        if not values:
            raise HazardLibraryTemplateAssessmentError(
                "Vyberte alespoň jednu ohroženou skupinu.",
            )

        validated: list[ExposedTargetRef] = []
        seen: set[tuple[str, int]] = set()
        for ref in values:
            if ref.key in seen:
                continue
            if ref.source_type == SOURCE_TYPE_ROLE:
                role = responsibility_role_service.get_by_id(ref.source_id)
                if role is None:
                    raise HazardLibraryTemplateAssessmentError(
                        "Vybraná funkce / role neexistuje.",
                    )
                if not role.active:
                    raise HazardLibraryTemplateAssessmentError(
                        "Lze vybrat pouze aktivní funkci / roli z číselníku.",
                    )
            elif ref.source_type == SOURCE_TYPE_HAZARD_GROUP:
                group = exposed_group_service.get_by_id(ref.source_id)
                if group is None:
                    raise HazardLibraryTemplateAssessmentError(
                        "Vybraná ohrožená skupina neexistuje.",
                    )
                if not group.active:
                    raise HazardLibraryTemplateAssessmentError(
                        "Lze vybrat pouze aktivní ohroženou skupinu z číselníku.",
                    )
            else:
                raise HazardLibraryTemplateAssessmentError(
                    "Neplatný zdroj ohrožené skupiny.",
                )
            seen.add(ref.key)
            validated.append(ref)
        return validated

    def _validate_exposed_group_ids(
        self,
        exposed_group_ids: list[int] | tuple[int, ...] | None,
        *,
        legacy_single_id: int | None,
    ) -> list[int]:
        refs = self._validate_target_refs(
            None,
            exposed_group_ids=exposed_group_ids,
            legacy_single_id=legacy_single_id,
        )
        return [
            ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]

    def _validate_severity(self, severity: str) -> str:
        if severity not in RISK_SEVERITIES:
            raise HazardLibraryTemplateAssessmentError("Neplatná závažnost následku.")
        return severity

    def _validate_event(self, template_id: int, template_event_id: int) -> None:
        event = hazard_library_template_event_service.get_by_id(template_event_id)
        if event is None:
            raise HazardLibraryTemplateAssessmentError("Nežádoucí událost zdroje rizika neexistuje.")
        event_template_id = hazard_library_template_event_service.get_template_id_for_event(
            event.id
        )
        if event_template_id != template_id:
            raise HazardLibraryTemplateAssessmentError(
                "Nežádoucí událost nepatří do zvoleného zdroje rizika."
            )

    def _validate_unique_active_refs(
        self,
        template_event_id: int,
        *,
        target_refs: list[ExposedTargetRef],
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active or not target_refs:
            return

        wanted = {ref.key for ref in target_refs}
        for assessment in self.repository.get_for_event(template_event_id, include_inactive=True):
            if assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            other_refs = self.group_repository.list_refs(assessment.id)
            if not other_refs and assessment.exposed_group_id:
                other_refs = [
                    ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, assessment.exposed_group_id)
                ]
            overlap = wanted & {ref.key for ref in other_refs}
            if not overlap:
                continue
            source_type, source_id = next(iter(overlap))
            group_name = resolve_exposed_target_display_name(
                ExposedTargetRef(source_type, source_id)
            )
            raise HazardLibraryTemplateAssessmentError(
                f"Pro tuto událost již existuje aktivní posouzení "
                f"pro ohroženou skupinu „{group_name}“."
            )

    def _validate_unique_active_groups(
        self,
        template_event_id: int,
        *,
        exposed_group_ids: list[int],
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        self._validate_unique_active_refs(
            template_event_id,
            target_refs=refs_from_legacy_group_ids(exposed_group_ids),
            exclude_assessment_id=exclude_assessment_id,
            active=active,
        )


hazard_library_template_assessment_service = HazardLibraryTemplateAssessmentService()
