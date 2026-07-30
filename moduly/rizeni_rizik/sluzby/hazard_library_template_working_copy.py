"""Pracovní kopie editoru Katalogu zdrojů rizik (UX-SAVE-1b).

Veškeré změny obsahu během editace probíhají pouze v paměti.
Do DB se zapisuje až při finálním Uložit v jedné transakci.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from core.ai_oponentni.modely.ai_proposal_package import (
    PACKAGE_STATUS_INCORPORATED,
    PACKAGE_STATUS_PENDING,
    PACKAGE_STATUS_REJECTED,
    AiProposalPackageRecord,
)
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.database.session import get_session
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.constants import (
    RISK_SEVERITIES,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
    HAZARD_LIBRARY_REVISION_REASON_MANUAL,
)
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
    HazardLibraryTemplateAssessmentExposedGroup,
)
from moduly.rizeni_rizik.modely.hazard_library_template_event import (
    HazardLibraryTemplateEvent,
)
from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
    HazardLibraryTemplateLegalLink,
)
from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateExistingMeasure,
    HazardLibraryTemplateRequiredMeasure,
)
from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
    HazardLibraryTemplateRevision,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    HazardLibraryTemplateAssessmentError,
    HazardLibraryTemplateAssessmentRow,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    HazardLibraryTemplateEventError,
    normalize_template_event_name,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    HazardLibraryTemplateExistingMeasureError,
    normalize_template_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
    HazardLibraryTemplateLegalLinkError,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    HazardLibraryTemplateRequiredMeasureError,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SOURCE_TYPE_HAZARD_GROUP,
    ExposedTargetRef,
    format_exposed_target_names,
    legacy_exposed_group_id,
    refs_from_legacy_group_ids,
    resolve_exposed_target_display_name,
)


@dataclass
class WcMeasure:
    id: int
    template_assessment_id: int
    description: str
    note: str = ""
    active: bool = True
    sort_order: int = 0


@dataclass
class WcAssessment:
    id: int
    template_event_id: int
    exposed_group_id: int | None
    exposed_group_ids: list[int] = field(default_factory=list)
    target_refs: list[ExposedTargetRef] = field(default_factory=list)
    severity: str = ""
    conclusion: str = ""
    note: str = ""
    active: bool = True
    sort_order: int = 0
    existing_measures: list[WcMeasure] = field(default_factory=list)
    required_measures: list[WcMeasure] = field(default_factory=list)


@dataclass
class WcEvent:
    id: int
    template_id: int
    name: str
    description: str = ""
    note: str = ""
    active: bool = True
    sort_order: int = 0
    assessments: list[WcAssessment] = field(default_factory=list)


@dataclass
class WcLegalLink:
    id: int
    template_id: int
    legal_document_id: int | None = None
    legal_requirement_id: int | None = None
    note: str = ""
    active: bool = True
    sort_order: int = 0


class HazardLibraryTemplateWorkingCopy:
    """In-memory strom obsahu MASTER zdroje rizika."""

    def __init__(self, template_id: int):
        self.template_id = template_id
        self.events: list[WcEvent] = []
        self.legal_links: list[WcLegalLink] = []
        self._next_temp_id = -1
        self._dirty = False
        self._pending_package_ids: list[int] = []
        self._pending_change_reason: str | None = None

    @classmethod
    def load(cls, template_id: int) -> HazardLibraryTemplateWorkingCopy:
        wc = cls(template_id)
        session = get_session()
        try:
            events = list(
                session.scalars(
                    select(HazardLibraryTemplateEvent)
                    .where(HazardLibraryTemplateEvent.template_id == template_id)
                    .order_by(
                        HazardLibraryTemplateEvent.sort_order,
                        HazardLibraryTemplateEvent.name,
                        HazardLibraryTemplateEvent.id,
                    ),
                ),
            )
            for event in events:
                wc_event = WcEvent(
                    id=int(event.id),
                    template_id=template_id,
                    name=event.name,
                    description=event.description or "",
                    note=event.note or "",
                    active=bool(event.active),
                    sort_order=int(event.sort_order or 0),
                )
                assessments = list(
                    session.scalars(
                        select(HazardLibraryTemplateAssessment)
                        .where(
                            HazardLibraryTemplateAssessment.template_event_id == event.id,
                        )
                        .order_by(
                            HazardLibraryTemplateAssessment.sort_order,
                            HazardLibraryTemplateAssessment.id,
                        ),
                    ),
                )
                for assessment in assessments:
                    join_rows = list(
                        session.execute(
                            select(
                                HazardLibraryTemplateAssessmentExposedGroup.source_type,
                                HazardLibraryTemplateAssessmentExposedGroup.exposed_group_id,
                            )
                            .where(
                                HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                                == assessment.id,
                            )
                            .order_by(HazardLibraryTemplateAssessmentExposedGroup.sort_order),
                        ),
                    )
                    target_refs = [
                        ExposedTargetRef(
                            str(source_type or SOURCE_TYPE_HAZARD_GROUP),
                            int(source_id),
                        )
                        for source_type, source_id in join_rows
                    ]
                    if not target_refs and assessment.exposed_group_id:
                        target_refs = [
                            ExposedTargetRef(
                                SOURCE_TYPE_HAZARD_GROUP,
                                int(assessment.exposed_group_id),
                            )
                        ]
                    group_ids = [
                        ref.source_id
                        for ref in target_refs
                        if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
                    ]
                    wc_assessment = WcAssessment(
                        id=int(assessment.id),
                        template_event_id=int(event.id),
                        exposed_group_id=legacy_exposed_group_id(target_refs),
                        exposed_group_ids=group_ids,
                        target_refs=target_refs,
                        severity=assessment.severity or "",
                        conclusion=assessment.conclusion or "",
                        note=assessment.note or "",
                        active=bool(assessment.active),
                        sort_order=int(assessment.sort_order or 0),
                    )
                    existing = list(
                        session.scalars(
                            select(HazardLibraryTemplateExistingMeasure)
                            .where(
                                HazardLibraryTemplateExistingMeasure.template_assessment_id
                                == assessment.id,
                            )
                            .order_by(
                                HazardLibraryTemplateExistingMeasure.sort_order,
                                HazardLibraryTemplateExistingMeasure.id,
                            ),
                        ),
                    )
                    for measure in existing:
                        wc_assessment.existing_measures.append(
                            WcMeasure(
                                id=int(measure.id),
                                template_assessment_id=int(assessment.id),
                                description=measure.description or "",
                                note=measure.note or "",
                                active=bool(measure.active),
                                sort_order=int(measure.sort_order or 0),
                            ),
                        )
                    required = list(
                        session.scalars(
                            select(HazardLibraryTemplateRequiredMeasure)
                            .where(
                                HazardLibraryTemplateRequiredMeasure.template_assessment_id
                                == assessment.id,
                            )
                            .order_by(
                                HazardLibraryTemplateRequiredMeasure.sort_order,
                                HazardLibraryTemplateRequiredMeasure.id,
                            ),
                        ),
                    )
                    for measure in required:
                        wc_assessment.required_measures.append(
                            WcMeasure(
                                id=int(measure.id),
                                template_assessment_id=int(assessment.id),
                                description=measure.description or "",
                                note=measure.note or "",
                                active=bool(measure.active),
                                sort_order=int(measure.sort_order or 0),
                            ),
                        )
                    wc_event.assessments.append(wc_assessment)
                wc.events.append(wc_event)

            links = list(
                session.scalars(
                    select(HazardLibraryTemplateLegalLink)
                    .where(HazardLibraryTemplateLegalLink.template_id == template_id)
                    .order_by(
                        HazardLibraryTemplateLegalLink.sort_order,
                        HazardLibraryTemplateLegalLink.id,
                    ),
                ),
            )
            for link in links:
                wc.legal_links.append(
                    WcLegalLink(
                        id=int(link.id),
                        template_id=template_id,
                        legal_document_id=(
                            int(link.legal_document_id)
                            if link.legal_document_id is not None
                            else None
                        ),
                        legal_requirement_id=(
                            int(link.legal_requirement_id)
                            if link.legal_requirement_id is not None
                            else None
                        ),
                        note=link.note or "",
                        active=bool(link.active),
                        sort_order=int(link.sort_order or 0),
                    ),
                )
        finally:
            session.close()
        wc._dirty = False
        return wc

    @property
    def is_dirty(self) -> bool:
        return self._dirty or bool(self._pending_package_ids)

    @property
    def pending_package_ids(self) -> list[int]:
        return list(self._pending_package_ids)

    def mark_clean(self) -> None:
        self._dirty = False
        self._pending_package_ids.clear()
        self._pending_change_reason = None

    def _touch(self, *, change_reason: str | None = None) -> None:
        self._dirty = True
        if change_reason is not None:
            self._pending_change_reason = change_reason

    def _alloc_id(self) -> int:
        value = self._next_temp_id
        self._next_temp_id -= 1
        return value

    def queue_package_incorporate(self, package_record_id: int) -> None:
        if package_record_id not in self._pending_package_ids:
            self._pending_package_ids.append(package_record_id)
        self._touch(change_reason=HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS)

    def clone(self) -> HazardLibraryTemplateWorkingCopy:
        """Bezpečně oddělená kopie pro atomické zapracování AI balíku."""
        cloned = HazardLibraryTemplateWorkingCopy(self.template_id)
        cloned.events = copy.deepcopy(self.events)
        cloned.legal_links = copy.deepcopy(self.legal_links)
        cloned._next_temp_id = self._next_temp_id
        cloned._dirty = self._dirty
        cloned._pending_package_ids = list(self._pending_package_ids)
        cloned._pending_change_reason = self._pending_change_reason
        return cloned

    def replace_content_from(self, other: HazardLibraryTemplateWorkingCopy) -> None:
        """Nahradí obsah této instance výsledkem kandidátní kopie."""
        if other.template_id != self.template_id:
            raise ValueError("Nelze nahradit obsah z jiné šablony.")
        self.events = other.events
        self.legal_links = other.legal_links
        self._next_temp_id = other._next_temp_id
        self._dirty = other._dirty
        self._pending_package_ids = list(other._pending_package_ids)
        self._pending_change_reason = other._pending_change_reason

    # --- Events -----------------------------------------------------------------

    def get_events(self, *, include_inactive: bool = True) -> list[WcEvent]:
        rows = self.events
        if not include_inactive:
            rows = [event for event in rows if event.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.name.casefold(), row.id))

    def get_event(self, event_id: int | None) -> WcEvent | None:
        if not event_id:
            return None
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    def count_active_assessments_by_events(self) -> dict[int, int]:
        return {
            event.id: sum(1 for assessment in event.assessments if assessment.active)
            for event in self.events
        }

    def create_event(
        self,
        *,
        template_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> WcEvent:
        if template_id != self.template_id:
            raise HazardLibraryTemplateEventError("Událost nepatří do zvoleného zdroje rizika.")
        normalized = name.strip()
        if not normalized:
            raise HazardLibraryTemplateEventError("Název události je povinný.")
        self._validate_unique_event_name(normalized, exclude_event_id=None, active=active)
        sort_order = max((event.sort_order for event in self.events), default=0) + 1
        event = WcEvent(
            id=self._alloc_id(),
            template_id=template_id,
            name=normalized,
            description=description.strip(),
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        self.events.append(event)
        self._touch()
        return event

    def update_event(
        self,
        event_id: int,
        *,
        template_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> WcEvent | None:
        event = self.get_event(event_id)
        if event is None:
            return None
        if event.template_id != template_id:
            raise HazardLibraryTemplateEventError("Událost nepatří do zvoleného zdroje rizika.")
        normalized = name.strip()
        if not normalized:
            raise HazardLibraryTemplateEventError("Název události je povinný.")
        self._validate_unique_event_name(normalized, exclude_event_id=event_id, active=active)
        event.name = normalized
        event.description = description.strip()
        event.note = note.strip()
        event.active = active
        self._touch()
        return event

    def activate_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if event is None:
            return False
        self._validate_unique_event_name(event.name, exclude_event_id=event_id, active=True)
        event.active = True
        self._touch()
        return True

    def deactivate_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if event is None:
            return False
        event.active = False
        self._touch()
        return True

    def _validate_unique_event_name(
        self,
        name: str,
        *,
        exclude_event_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        key = normalize_template_event_name(name)
        for event in self.events:
            if exclude_event_id is not None and event.id == exclude_event_id:
                continue
            if event.active and normalize_template_event_name(event.name) == key:
                raise HazardLibraryTemplateEventError(
                    "Aktivní událost se stejným názvem již v tomto zdroji existuje.",
                )

    # --- Assessments ------------------------------------------------------------

    def get_assessment(self, assessment_id: int | None) -> WcAssessment | None:
        if not assessment_id:
            return None
        for event in self.events:
            for assessment in event.assessments:
                if assessment.id == assessment_id:
                    return assessment
        return None

    def get_group_ids(self, assessment_id: int) -> list[int]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        return list(assessment.exposed_group_ids)

    def get_target_refs(self, assessment_id: int) -> list[ExposedTargetRef]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        refs = list(assessment.target_refs)
        if refs:
            return refs
        return refs_from_legacy_group_ids(
            assessment.exposed_group_ids,
            legacy_single_id=assessment.exposed_group_id,
        )

    def get_assessments_for_event(
        self,
        template_event_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateAssessmentRow]:
        event = self.get_event(template_event_id)
        if event is None:
            return []
        rows: list[HazardLibraryTemplateAssessmentRow] = []
        for assessment in event.assessments:
            if not include_inactive and not assessment.active:
                continue
            rows.append(self._to_assessment_row(assessment))
        return sorted(
            rows,
            key=lambda row: (
                row.assessment.sort_order,
                row.exposed_group_name.casefold(),
                row.assessment.id,
            ),
        )

    def _to_assessment_row(self, assessment: WcAssessment) -> HazardLibraryTemplateAssessmentRow:
        refs = list(assessment.target_refs)
        if not refs:
            refs = refs_from_legacy_group_ids(
                assessment.exposed_group_ids,
                legacy_single_id=assessment.exposed_group_id,
            )
        names = format_exposed_target_names(refs)
        proxy = HazardLibraryTemplateAssessment(
            id=assessment.id,
            template_event_id=assessment.template_event_id,
            exposed_group_id=assessment.exposed_group_id,
            severity=assessment.severity,
            conclusion=assessment.conclusion,
            note=assessment.note,
            active=assessment.active,
            sort_order=assessment.sort_order,
        )
        return HazardLibraryTemplateAssessmentRow(
            assessment=proxy,
            exposed_group_name=names if names else "—",
            severity_label=format_risk_severity_label(assessment.severity),
            exposed_group_ids=tuple(
                ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
            ),
            target_refs=tuple(refs),
        )

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
        del template_id
        event = self.get_event(template_event_id)
        if event is None:
            raise HazardLibraryTemplateAssessmentError("Událost neexistuje.")
        refs = self._normalize_target_refs(target_refs, exposed_group_ids, exposed_group_id)
        group_ids = [
            ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]
        if severity not in RISK_SEVERITIES:
            raise HazardLibraryTemplateAssessmentError("Neplatná závažnost rizika.")
        self._validate_unique_refs(
            template_event_id,
            refs,
            exclude_assessment_id=None,
            active=active,
        )
        sort_order = max((a.sort_order for a in event.assessments), default=0) + 1
        assessment = WcAssessment(
            id=self._alloc_id(),
            template_event_id=template_event_id,
            exposed_group_id=legacy_exposed_group_id(refs),
            exposed_group_ids=list(group_ids),
            target_refs=list(refs),
            severity=severity,
            conclusion=conclusion.strip(),
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        event.assessments.append(assessment)
        self._touch()
        return self._assessment_proxy(assessment)

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
        del template_id
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return None
        if assessment.template_event_id != template_event_id:
            raise HazardLibraryTemplateAssessmentError(
                "Posouzení nepatří do zvolené události.",
            )
        refs = self._normalize_target_refs(target_refs, exposed_group_ids, exposed_group_id)
        group_ids = [
            ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]
        if severity not in RISK_SEVERITIES:
            raise HazardLibraryTemplateAssessmentError("Neplatná závažnost rizika.")
        self._validate_unique_refs(
            template_event_id,
            refs,
            exclude_assessment_id=assessment_id,
            active=active,
        )
        assessment.exposed_group_id = legacy_exposed_group_id(refs)
        assessment.exposed_group_ids = list(group_ids)
        assessment.target_refs = list(refs)
        assessment.severity = severity
        assessment.conclusion = conclusion.strip()
        assessment.note = note.strip()
        assessment.active = active
        self._touch()
        return self._assessment_proxy(assessment)

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return False
        refs = list(assessment.target_refs) or refs_from_legacy_group_ids(
            assessment.exposed_group_ids,
            legacy_single_id=assessment.exposed_group_id,
        )
        self._validate_unique_refs(
            assessment.template_event_id,
            refs,
            exclude_assessment_id=assessment_id,
            active=True,
        )
        assessment.active = True
        self._touch()
        return True

    def deactivate_assessment(self, assessment_id: int) -> bool:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return False
        assessment.active = False
        self._touch()
        return True

    def _assessment_proxy(self, assessment: WcAssessment) -> HazardLibraryTemplateAssessment:
        return HazardLibraryTemplateAssessment(
            id=assessment.id,
            template_event_id=assessment.template_event_id,
            exposed_group_id=assessment.exposed_group_id,
            severity=assessment.severity,
            conclusion=assessment.conclusion,
            note=assessment.note,
            active=assessment.active,
            sort_order=assessment.sort_order,
        )

    def _normalize_target_refs(
        self,
        target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
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
        unique: list[ExposedTargetRef] = []
        seen: set[tuple[str, int]] = set()
        for ref in values:
            if ref.key in seen:
                continue
            seen.add(ref.key)
            unique.append(ref)
        if not unique:
            raise HazardLibraryTemplateAssessmentError("Vyberte alespoň jednu ohroženou skupinu.")
        return unique

    def _normalize_group_ids(
        self,
        exposed_group_ids: list[int] | tuple[int, ...] | None,
        legacy_single_id: int | None,
    ) -> list[int]:
        refs = self._normalize_target_refs(None, exposed_group_ids, legacy_single_id)
        return [
            ref.source_id for ref in refs if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]

    def _validate_unique_refs(
        self,
        template_event_id: int,
        target_refs: list[ExposedTargetRef],
        *,
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        event = self.get_event(template_event_id)
        if event is None:
            return
        wanted = {ref.key for ref in target_refs}
        for assessment in event.assessments:
            if exclude_assessment_id is not None and assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            other = list(assessment.target_refs) or refs_from_legacy_group_ids(
                assessment.exposed_group_ids,
                legacy_single_id=assessment.exposed_group_id,
            )
            if wanted.intersection({ref.key for ref in other}):
                raise HazardLibraryTemplateAssessmentError(
                    "Aktivní posouzení se stejným ohroženým skupinami již existuje.",
                )

    def _validate_unique_groups(
        self,
        template_event_id: int,
        group_ids: list[int],
        *,
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        self._validate_unique_refs(
            template_event_id,
            refs_from_legacy_group_ids(group_ids),
            exclude_assessment_id=exclude_assessment_id,
            active=active,
        )

    # --- Measures ---------------------------------------------------------------

    def get_existing_measures(
        self,
        assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[WcMeasure]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        rows = assessment.existing_measures
        if not include_inactive:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.id))

    def get_required_measures(
        self,
        assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[WcMeasure]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        rows = assessment.required_measures
        if not include_inactive:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.id))

    def get_existing_measure(self, measure_id: int | None) -> WcMeasure | None:
        if not measure_id:
            return None
        for event in self.events:
            for assessment in event.assessments:
                for measure in assessment.existing_measures:
                    if measure.id == measure_id:
                        return measure
        return None

    def get_required_measure(self, measure_id: int | None) -> WcMeasure | None:
        if not measure_id:
            return None
        for event in self.events:
            for assessment in event.assessments:
                for measure in assessment.required_measures:
                    if measure.id == measure_id:
                        return measure
        return None

    def create_existing_measure(
        self,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> WcMeasure:
        del template_id
        return self._create_measure(
            template_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=True,
        )

    def create_required_measure(
        self,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> WcMeasure:
        del template_id
        return self._create_measure(
            template_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=False,
        )

    def update_existing_measure(
        self,
        measure_id: int,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> WcMeasure | None:
        del template_id
        return self._update_measure(
            measure_id,
            template_assessment_id=template_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=True,
        )

    def update_required_measure(
        self,
        measure_id: int,
        *,
        template_id: int,
        template_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> WcMeasure | None:
        del template_id
        return self._update_measure(
            measure_id,
            template_assessment_id=template_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=False,
        )

    def activate_existing_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, True, existing=True)

    def deactivate_existing_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, False, existing=True)

    def activate_required_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, True, existing=False)

    def deactivate_required_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, False, existing=False)

    def _create_measure(
        self,
        template_assessment_id: int,
        *,
        description: str,
        note: str,
        active: bool,
        existing: bool,
    ) -> WcMeasure:
        assessment = self.get_assessment(template_assessment_id)
        if assessment is None:
            raise (
                HazardLibraryTemplateExistingMeasureError
                if existing
                else HazardLibraryTemplateRequiredMeasureError
            )("Posouzení neexistuje.")
        normalized = description.strip()
        if not normalized:
            raise (
                HazardLibraryTemplateExistingMeasureError
                if existing
                else HazardLibraryTemplateRequiredMeasureError
            )("Popis opatření je povinný.")
        bucket = assessment.existing_measures if existing else assessment.required_measures
        self._validate_unique_measure(
            bucket,
            description=normalized,
            exclude_measure_id=None,
            active=active,
            existing=existing,
        )
        sort_order = max((row.sort_order for row in bucket), default=0) + 1
        measure = WcMeasure(
            id=self._alloc_id(),
            template_assessment_id=template_assessment_id,
            description=normalized,
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        bucket.append(measure)
        self._touch()
        return measure

    def _update_measure(
        self,
        measure_id: int,
        *,
        template_assessment_id: int,
        description: str,
        note: str,
        active: bool,
        existing: bool,
    ) -> WcMeasure | None:
        measure = (
            self.get_existing_measure(measure_id)
            if existing
            else self.get_required_measure(measure_id)
        )
        if measure is None:
            return None
        assessment = self.get_assessment(template_assessment_id)
        if assessment is None or measure.template_assessment_id != template_assessment_id:
            raise (
                HazardLibraryTemplateExistingMeasureError
                if existing
                else HazardLibraryTemplateRequiredMeasureError
            )("Opatření nepatří do zvoleného posouzení.")
        normalized = description.strip()
        if not normalized:
            raise (
                HazardLibraryTemplateExistingMeasureError
                if existing
                else HazardLibraryTemplateRequiredMeasureError
            )("Popis opatření je povinný.")
        bucket = assessment.existing_measures if existing else assessment.required_measures
        self._validate_unique_measure(
            bucket,
            description=normalized,
            exclude_measure_id=measure_id,
            active=active,
            existing=existing,
        )
        measure.description = normalized
        measure.note = note.strip()
        measure.active = active
        self._touch()
        return measure

    def _set_measure_active(self, measure_id: int, active: bool, *, existing: bool) -> bool:
        measure = (
            self.get_existing_measure(measure_id)
            if existing
            else self.get_required_measure(measure_id)
        )
        if measure is None:
            return False
        if active:
            assessment = self.get_assessment(measure.template_assessment_id)
            if assessment is None:
                return False
            bucket = assessment.existing_measures if existing else assessment.required_measures
            self._validate_unique_measure(
                bucket,
                description=measure.description,
                exclude_measure_id=measure_id,
                active=True,
                existing=existing,
            )
        measure.active = active
        self._touch()
        return True

    def _validate_unique_measure(
        self,
        bucket: list[WcMeasure],
        *,
        description: str,
        exclude_measure_id: int | None,
        active: bool,
        existing: bool,
    ) -> None:
        if not active:
            return
        key = normalize_template_measure_description(description)
        for measure in bucket:
            if exclude_measure_id is not None and measure.id == exclude_measure_id:
                continue
            if measure.active and normalize_template_measure_description(measure.description) == key:
                raise (
                    HazardLibraryTemplateExistingMeasureError
                    if existing
                    else HazardLibraryTemplateRequiredMeasureError
                )("Aktivní opatření se stejným popisem již existuje.")

    # --- Legal links ------------------------------------------------------------

    def get_legal_links(self, *, include_inactive: bool = True) -> list[WcLegalLink]:
        rows = self.legal_links
        if not include_inactive:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.id))

    def get_legal_link(self, link_id: int | None) -> WcLegalLink | None:
        if not link_id:
            return None
        for link in self.legal_links:
            if link.id == link_id:
                return link
        return None

    def create_legal_link(
        self,
        *,
        template_id: int,
        legal_document_id: int,
        legal_requirement_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> WcLegalLink:
        del legal_requirement_id
        if template_id != self.template_id:
            raise HazardLibraryTemplateLegalLinkError(
                "Právní vazba nepatří do zvoleného zdroje rizika.",
            )
        document_id = int(legal_document_id)
        self._validate_unique_document(document_id, exclude_link_id=None, active=active)
        sort_order = max((link.sort_order for link in self.legal_links), default=0) + 1
        link = WcLegalLink(
            id=self._alloc_id(),
            template_id=template_id,
            legal_document_id=document_id,
            legal_requirement_id=None,
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        self.legal_links.append(link)
        self._touch()
        return link

    def update_legal_link(
        self,
        link_id: int,
        *,
        template_id: int,
        legal_document_id: int,
        legal_requirement_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> WcLegalLink | None:
        del legal_requirement_id
        link = self.get_legal_link(link_id)
        if link is None:
            return None
        if link.template_id != template_id:
            raise HazardLibraryTemplateLegalLinkError(
                "Právní vazba nepatří do zvoleného zdroje rizika.",
            )
        document_id = int(legal_document_id)
        self._validate_unique_document(document_id, exclude_link_id=link_id, active=active)
        link.legal_document_id = document_id
        link.legal_requirement_id = None
        link.note = note.strip()
        link.active = active
        self._touch()
        return link

    def activate_legal_link(self, link_id: int) -> bool:
        link = self.get_legal_link(link_id)
        if link is None:
            return False
        if link.legal_document_id is not None:
            self._validate_unique_document(
                link.legal_document_id,
                exclude_link_id=link_id,
                active=True,
            )
        link.active = True
        self._touch()
        return True

    def deactivate_legal_link(self, link_id: int) -> bool:
        link = self.get_legal_link(link_id)
        if link is None:
            return False
        link.active = False
        self._touch()
        return True

    def _validate_unique_document(
        self,
        legal_document_id: int,
        *,
        exclude_link_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        for link in self.legal_links:
            if exclude_link_id is not None and link.id == exclude_link_id:
                continue
            if link.active and link.legal_document_id == legal_document_id:
                raise HazardLibraryTemplateLegalLinkError(
                    "Aktivní vazba na stejný právní předpis již existuje.",
                )

    # --- Commit -----------------------------------------------------------------

    def commit(
        self,
        *,
        basics: dict[str, Any] | None = None,
        bump_revision: bool = True,
    ) -> HazardLibraryTemplate:
        """Zapíše pracovní kopii do DB v jedné transakci."""
        session = get_session()
        try:
            template = session.get(HazardLibraryTemplate, self.template_id)
            if template is None:
                raise ValueError("Zdroj rizika neexistuje.")

            if basics is not None:
                template.name = basics["name"]
                template.category = basics["category"]
                template.description = basics.get("description", "")
                template.note = basics.get("note", "")
                template.active = bool(basics.get("active", True))
                if "application_scope" in basics:
                    template.application_scope = basics["application_scope"]
                template.updated_at = datetime.now()

            id_map: dict[int, int] = {}
            self._commit_events(session, id_map)
            self._commit_legal_links(session)

            pending_packages = list(self._pending_package_ids)
            for package_id in pending_packages:
                record = session.get(AiProposalPackageRecord, package_id)
                if record is not None and record.status == PACKAGE_STATUS_PENDING:
                    record.status = PACKAGE_STATUS_INCORPORATED

            content_changed = self._dirty or bool(pending_packages)
            new_version = template.version_number
            if bump_revision and content_changed:
                template.version_number += 1
                template.updated_at = datetime.now()
                new_version = template.version_number
                if pending_packages:
                    reason = (
                        self._pending_change_reason
                        or HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS
                    )
                else:
                    reason = (
                        self._pending_change_reason
                        or HAZARD_LIBRARY_REVISION_REASON_MANUAL
                    )
                session.add(
                    HazardLibraryTemplateRevision(
                        template_id=template.id,
                        revision_number=new_version,
                        change_reason=reason,
                    ),
                )

            review_ids = {
                int(record.ai_peer_review_id)
                for package_id in pending_packages
                if (record := session.get(AiProposalPackageRecord, package_id)) is not None
            }

            session.commit()
            session.refresh(template)
            template_id = int(template.id)
            version_number = int(template.version_number)
            name = template.name
            category = template.category
            description = template.description or ""
            note = template.note or ""
            active = bool(template.active)
            application_scope = template.application_scope
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        for review_id in review_ids:
            self._refresh_review_counts(review_id)
        self.mark_clean()
        reloaded = HazardLibraryTemplateWorkingCopy.load(self.template_id)
        self.events = reloaded.events
        self.legal_links = reloaded.legal_links
        self._next_temp_id = reloaded._next_temp_id
        return HazardLibraryTemplate(
            id=template_id,
            name=name,
            category=category,
            description=description,
            note=note,
            active=active,
            application_scope=application_scope,
            version_number=version_number,
        )

    def _commit_events(self, session, id_map: dict[int, int]) -> None:
        for event in self.events:
            if event.id > 0:
                db_event = session.get(HazardLibraryTemplateEvent, event.id)
                if db_event is None:
                    continue
                db_event.name = event.name
                db_event.description = event.description
                db_event.note = event.note
                db_event.active = event.active
                db_event.sort_order = event.sort_order
                db_event.updated_at = datetime.now()
                event_db_id = int(db_event.id)
            else:
                db_event = HazardLibraryTemplateEvent(
                    template_id=self.template_id,
                    name=event.name,
                    description=event.description,
                    note=event.note,
                    active=event.active,
                    sort_order=event.sort_order,
                )
                session.add(db_event)
                session.flush()
                event_db_id = int(db_event.id)
                id_map[event.id] = event_db_id
            for assessment in event.assessments:
                self._commit_assessment(session, assessment, event_db_id, id_map)

    def _commit_assessment(
        self,
        session,
        assessment: WcAssessment,
        event_db_id: int,
        id_map: dict[int, int],
    ) -> None:
        if assessment.id > 0:
            db_assessment = session.get(HazardLibraryTemplateAssessment, assessment.id)
            if db_assessment is None:
                return
            db_assessment.template_event_id = event_db_id
            db_assessment.exposed_group_id = assessment.exposed_group_id
            db_assessment.severity = assessment.severity
            db_assessment.conclusion = assessment.conclusion
            db_assessment.note = assessment.note
            db_assessment.active = assessment.active
            db_assessment.sort_order = assessment.sort_order
            db_assessment.updated_at = datetime.now()
            assessment_db_id = int(db_assessment.id)
        else:
            db_assessment = HazardLibraryTemplateAssessment(
                template_event_id=event_db_id,
                exposed_group_id=assessment.exposed_group_id,
                severity=assessment.severity,
                conclusion=assessment.conclusion,
                note=assessment.note,
                active=assessment.active,
                sort_order=assessment.sort_order,
            )
            session.add(db_assessment)
            session.flush()
            assessment_db_id = int(db_assessment.id)
            id_map[assessment.id] = assessment_db_id

        session.execute(
            delete(HazardLibraryTemplateAssessmentExposedGroup).where(
                HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                == assessment_db_id,
            ),
        )
        refs = list(assessment.target_refs) or refs_from_legacy_group_ids(
            assessment.exposed_group_ids,
            legacy_single_id=assessment.exposed_group_id,
        )
        for sort_order, ref in enumerate(refs, start=1):
            session.add(
                HazardLibraryTemplateAssessmentExposedGroup(
                    assessment_id=assessment_db_id,
                    exposed_group_id=ref.source_id,
                    source_type=ref.source_type,
                    sort_order=sort_order,
                ),
            )

        for measure in assessment.existing_measures:
            self._commit_measure(
                session,
                measure,
                assessment_db_id,
                existing=True,
                id_map=id_map,
            )
        for measure in assessment.required_measures:
            self._commit_measure(
                session,
                measure,
                assessment_db_id,
                existing=False,
                id_map=id_map,
            )

    def _commit_measure(
        self,
        session,
        measure: WcMeasure,
        assessment_db_id: int,
        *,
        existing: bool,
        id_map: dict[int, int],
    ) -> None:
        model_cls = (
            HazardLibraryTemplateExistingMeasure
            if existing
            else HazardLibraryTemplateRequiredMeasure
        )
        if measure.id > 0:
            db_measure = session.get(model_cls, measure.id)
            if db_measure is None:
                return
            db_measure.template_assessment_id = assessment_db_id
            db_measure.description = measure.description
            db_measure.note = measure.note
            db_measure.active = measure.active
            db_measure.sort_order = measure.sort_order
            db_measure.updated_at = datetime.now()
            return
        db_measure = model_cls(
            template_assessment_id=assessment_db_id,
            description=measure.description,
            note=measure.note,
            active=measure.active,
            sort_order=measure.sort_order,
        )
        session.add(db_measure)
        session.flush()
        id_map[measure.id] = int(db_measure.id)

    def _commit_legal_links(self, session) -> None:
        for link in self.legal_links:
            if link.id > 0:
                db_link = session.get(HazardLibraryTemplateLegalLink, link.id)
                if db_link is None:
                    continue
                db_link.legal_document_id = link.legal_document_id
                db_link.legal_requirement_id = None
                db_link.note = link.note
                db_link.active = link.active
                db_link.sort_order = link.sort_order
                db_link.updated_at = datetime.now()
                continue
            session.add(
                HazardLibraryTemplateLegalLink(
                    template_id=self.template_id,
                    legal_document_id=link.legal_document_id,
                    legal_requirement_id=None,
                    note=link.note,
                    active=link.active,
                    sort_order=link.sort_order,
                ),
            )

    @staticmethod
    def _refresh_review_counts(review_id: int) -> None:
        package_repo = AiProposalPackageRepository()
        review_repo = AiPeerReviewRepository()
        packages = package_repo.get_for_review(review_id)
        review = review_repo.get_by_id(review_id)
        if review is None:
            return
        review.pending_proposals_count = sum(
            1 for item in packages if item.status == PACKAGE_STATUS_PENDING
        )
        review.rejected_count = sum(
            1 for item in packages if item.status == PACKAGE_STATUS_REJECTED
        )
        review.accepted_count = sum(
            1 for item in packages if item.status == PACKAGE_STATUS_INCORPORATED
        )
        review.unassigned_count = 0
        review_repo.update(review)


def find_catalog_working_copy(widget) -> HazardLibraryTemplateWorkingCopy | None:
    """Najde pracovní kopii na rodičovském editoru katalogu."""
    current = widget
    while current is not None:
        store = getattr(current, "_content_store", None)
        if isinstance(store, HazardLibraryTemplateWorkingCopy):
            return store
        parent_fn = getattr(current, "parent", None)
        current = parent_fn() if callable(parent_fn) else None
    return None
