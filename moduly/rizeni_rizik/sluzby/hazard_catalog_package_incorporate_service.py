"""Zapracování návrhových balíků AI do MASTER katalogu (R20b, slučování R20g)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
)
from core.ai_oponentni.modely.ai_proposal_package import (
    PACKAGE_STATUS_INCORPORATED,
    PACKAGE_STATUS_PENDING,
    PACKAGE_STATUS_REJECTED,
    AiProposalPackageRecord,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.database.session import get_session
from moduly.nastaveni.sluzby.exposed_group_service import (
    ExposedGroupMatchKind,
    exposed_group_service,
)
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.constants_library import (
    CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP,
    CATALOG_INCORPORATE_ERROR_EVENT_PARENT,
    CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH,
    CATALOG_INCORPORATE_ERROR_REVIEW_MISSING,
    CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE,
    CATALOG_INCORPORATE_ERROR_SOURCE_MISSING,
    HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
)
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
    HazardLibraryTemplateAssessmentExposedGroup,
)
from moduly.rizeni_rizik.modely.hazard_library_template_event import HazardLibraryTemplateEvent
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
from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
    LegalDocumentMatchKind,
    hazard_catalog_legal_document_resolver,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
    HazardCatalogProposalIncorporateService,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    normalize_template_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardCatalogPackageIncorporateError(ValueError):
    pass


@dataclass(frozen=True)
class AmbiguousAssessmentCandidate:
    assessment_id: int
    severity: str
    severity_label: str
    conclusion: str
    group_names: str


class HazardCatalogPackageAmbiguousGroupError(HazardCatalogPackageIncorporateError):
    """Více aktivních posouzení obsahuje stejnou ohroženou skupinu."""

    def __init__(
        self,
        *,
        group_id: int,
        group_name: str,
        candidates: tuple[AmbiguousAssessmentCandidate, ...],
    ):
        self.group_id = group_id
        self.group_name = group_name
        self.candidates = candidates
        super().__init__(
            f"Ohrožená skupina „{group_name}“ je ve více aktivních posouzeních. "
            "Vyberte cílové posouzení.",
        )


@dataclass
class CatalogPackageIncorporateResult:
    package_record_id: int
    new_revision_number: int
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int
    legal_link_count: int
    merged_assessment_count: int = 0


class HazardCatalogPackageIncorporateService:
    def __init__(self):
        self.package_repository = AiProposalPackageRepository()
        self.review_repository = AiPeerReviewRepository()
        self._order = HazardCatalogProposalIncorporateService()

    def get_export_id_map(self, review_id: int) -> dict[str, dict]:
        review = self.review_repository.get_by_id(review_id)
        if review is None:
            return {}
        try:
            export_id_map = json.loads(review.export_id_map_json or "{}")
        except json.JSONDecodeError:
            export_id_map = {}
        return export_id_map if isinstance(export_id_map, dict) else {}

    def reject_package(self, package_record_id: int) -> bool:
        record = self.package_repository.get_by_id(package_record_id)
        if record is None or record.status != PACKAGE_STATUS_PENDING:
            return False
        record.status = PACKAGE_STATUS_REJECTED
        self.package_repository.update(record)
        self._refresh_review_counts(record.ai_peer_review_id)
        return True

    def update_package_payload(
        self,
        package_record_id: int,
        package: AiProposalPackage,
    ) -> AiProposalPackageRecord:
        record = self.package_repository.get_by_id(package_record_id)
        if record is None:
            raise HazardCatalogPackageIncorporateError("Návrhový balík neexistuje.")
        if record.status != PACKAGE_STATUS_PENDING:
            raise HazardCatalogPackageIncorporateError(
                "Upravovat lze pouze balík čekající na odborné posouzení.",
            )
        record.package_id = package.package_id
        record.package_type = package.package_type
        record.target_event_export_id = package.target_event_export_id or ""
        record.payload_json = json.dumps(package.to_storage_dict(), ensure_ascii=False)
        return self.package_repository.update(record)

    def incorporate_package(
        self,
        *,
        template_id: int,
        package_record_id: int,
        group_assessment_overrides: dict[int, int] | None = None,
    ) -> CatalogPackageIncorporateResult:
        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_MISSING)
        if not template.active:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE)

        record = self.package_repository.get_by_id(package_record_id)
        if record is None:
            raise HazardCatalogPackageIncorporateError("Návrhový balík neexistuje.")
        if record.status != PACKAGE_STATUS_PENDING:
            raise HazardCatalogPackageIncorporateError(
                "Zapracovat lze pouze balík čekající na odborné posouzení.",
            )
        if record.source_id != template_id:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH)

        review = self.review_repository.get_by_id(record.ai_peer_review_id)
        if review is None:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISSING)
        if review.source_id != template_id:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH)

        package = self.package_repository.package_from_record(record)
        export_id_map = self.get_export_id_map(record.ai_peer_review_id)
        overrides = {
            int(group_id): int(assessment_id)
            for group_id, assessment_id in (group_assessment_overrides or {}).items()
        }

        event_count = 0
        assessment_count = 0
        merged_assessment_count = 0
        existing_measure_count = 0
        required_measure_count = 0
        legal_link_count = 0
        new_revision_number = 0

        session = get_session()
        try:
            db_template = session.get(HazardLibraryTemplate, template_id)
            if db_template is None:
                raise HazardCatalogPackageIncorporateError(
                    CATALOG_INCORPORATE_ERROR_SOURCE_MISSING,
                )
            db_record = session.get(AiProposalPackageRecord, package_record_id)
            if db_record is None or db_record.status != PACKAGE_STATUS_PENDING:
                raise HazardCatalogPackageIncorporateError("Návrhový balík neexistuje.")

            event_id = self._resolve_or_create_event(
                session,
                template_id=template_id,
                package=package,
                export_id_map=export_id_map,
            )
            if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
                event_count = 1

            for assessment in package.assessments:
                created, merged, existing_added, required_added = (
                    self._incorporate_assessment(
                        session,
                        template_event_id=event_id,
                        assessment=assessment,
                        package_reasoning=package.reasoning,
                        group_assessment_overrides=overrides,
                    )
                )
                assessment_count += created
                merged_assessment_count += merged
                existing_measure_count += existing_added
                required_measure_count += required_added

            for link in package.legal_links:
                document_id = self._resolve_legal_document_id(link)
                session.add(
                    HazardLibraryTemplateLegalLink(
                        template_id=template_id,
                        legal_document_id=document_id,
                        legal_requirement_id=None,
                        note=self._build_legal_note(link, package.reasoning),
                        active=True,
                        sort_order=self._order._next_legal_link_sort_order(
                            session,
                            template_id,
                        ),
                    ),
                )
                legal_link_count += 1

            db_record.status = PACKAGE_STATUS_INCORPORATED
            db_template.version_number += 1
            db_template.updated_at = datetime.now()
            session.add(
                HazardLibraryTemplateRevision(
                    template_id=template_id,
                    revision_number=db_template.version_number,
                    change_reason=HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
                ),
            )
            new_revision_number = db_template.version_number
            session.commit()
        except HazardCatalogPackageIncorporateError:
            session.rollback()
            raise
        except Exception as error:
            session.rollback()
            raise HazardCatalogPackageIncorporateError(str(error)) from error
        finally:
            session.close()

        self._refresh_review_counts(record.ai_peer_review_id)
        return CatalogPackageIncorporateResult(
            package_record_id=package_record_id,
            new_revision_number=new_revision_number,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
            legal_link_count=legal_link_count,
            merged_assessment_count=merged_assessment_count,
        )

    def _resolve_or_create_event(
        self,
        session,
        *,
        template_id: int,
        package: AiProposalPackage,
        export_id_map: dict[str, dict],
    ) -> int:
        if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
            export_id = (package.target_event_export_id or "").strip()
            parent = export_id_map.get(export_id) if export_id else None
            if not isinstance(parent, dict) or parent.get("kind") != "event":
                raise HazardCatalogPackageIncorporateError(
                    CATALOG_INCORPORATE_ERROR_EVENT_PARENT.format(
                        name=package.event_name,
                    ),
                )
            return int(parent["id"])

        if package.package_type != AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
            raise HazardCatalogPackageIncorporateError(
                f"Nepodporovaný typ balíku „{package.package_type}“.",
            )
        if package.event is None or not package.event.name.strip():
            raise HazardCatalogPackageIncorporateError(
                "Balík typu nová událost musí obsahovat název události.",
            )
        event = HazardLibraryTemplateEvent(
            template_id=template_id,
            name=package.event.name.strip(),
            description=(package.event.description or "").strip(),
            note=self._join_notes(package.event.note, package.reasoning),
            active=True,
            sort_order=self._order._next_event_sort_order(session, template_id),
        )
        session.add(event)
        session.flush()
        return int(event.id)

    def _incorporate_assessment(
        self,
        session,
        *,
        template_event_id: int,
        assessment,
        package_reasoning: str,
        group_assessment_overrides: dict[int, int],
    ) -> tuple[int, int, int, int]:
        group_ids = self._resolve_exposed_group_ids(assessment)
        merge_targets: dict[int, HazardLibraryTemplateAssessment] = {}
        new_group_ids: list[int] = []

        for group_id in group_ids:
            matches = self._find_active_assessments_containing_group(
                session,
                template_event_id=template_event_id,
                group_id=group_id,
            )
            override_id = group_assessment_overrides.get(group_id)
            if override_id is not None:
                override = session.get(HazardLibraryTemplateAssessment, override_id)
                if (
                    override is None
                    or not override.active
                    or int(override.template_event_id) != int(template_event_id)
                ):
                    raise HazardCatalogPackageIncorporateError(
                        "Vybrané cílové posouzení pro ohroženou skupinu není platné.",
                    )
                matches = [override]

            if len(matches) > 1:
                group_name = (
                    exposed_group_service.display_name(group_id) or f"#{group_id}"
                )
                raise HazardCatalogPackageAmbiguousGroupError(
                    group_id=group_id,
                    group_name=group_name,
                    candidates=tuple(
                        self._to_ambiguous_candidate(session, row) for row in matches
                    ),
                )
            if len(matches) == 1:
                merge_targets[int(matches[0].id)] = matches[0]
            else:
                new_group_ids.append(group_id)

        existing_added = 0
        required_added = 0
        merged_count = 0

        for target in merge_targets.values():
            added_existing, added_required = self._merge_into_assessment(
                session,
                target=target,
                assessment=assessment,
                package_reasoning=package_reasoning,
            )
            existing_added += added_existing
            required_added += added_required
            merged_count += 1

        created_count = 0
        if new_group_ids:
            assessment_id = self._create_assessment(
                session,
                template_event_id=template_event_id,
                assessment=assessment,
                package_reasoning=package_reasoning,
                group_ids=new_group_ids,
            )
            created_count = 1
            for measure in assessment.existing_measures:
                description = (measure.description or "").strip()
                if not description:
                    continue
                session.add(
                    HazardLibraryTemplateExistingMeasure(
                        template_assessment_id=assessment_id,
                        description=description,
                        note=(measure.note or "").strip(),
                        active=True,
                        sort_order=self._order._next_existing_measure_sort_order(
                            session,
                            assessment_id,
                        ),
                    ),
                )
                existing_added += 1
            for measure in assessment.required_measures:
                description = (measure.description or "").strip()
                if not description:
                    continue
                session.add(
                    HazardLibraryTemplateRequiredMeasure(
                        template_assessment_id=assessment_id,
                        description=description,
                        note=(measure.note or "").strip(),
                        active=True,
                        sort_order=self._order._next_required_measure_sort_order(
                            session,
                            assessment_id,
                        ),
                    ),
                )
                required_added += 1

        return created_count, merged_count, existing_added, required_added

    def _merge_into_assessment(
        self,
        session,
        *,
        target: HazardLibraryTemplateAssessment,
        assessment,
        package_reasoning: str,
    ) -> tuple[int, int]:
        proposed_severity = (
            assessment.severity
            if assessment.severity in RISK_SEVERITIES
            else DEFAULT_RISK_SEVERITY
        )
        target.severity = self._stricter_severity(target.severity, proposed_severity)
        target.conclusion = self._merge_conclusions(
            target.conclusion or "",
            assessment.conclusion or "",
        )
        if package_reasoning.strip() and not (target.note or "").strip():
            target.note = package_reasoning.strip()
        target.updated_at = datetime.now()
        session.add(target)

        existing_added = self._add_unique_existing_measures(
            session,
            assessment_id=int(target.id),
            measures=assessment.existing_measures,
        )
        required_added = self._add_unique_required_measures(
            session,
            assessment_id=int(target.id),
            measures=assessment.required_measures,
        )
        return existing_added, required_added

    def _add_unique_existing_measures(self, session, *, assessment_id: int, measures) -> int:
        existing = session.scalars(
            select(HazardLibraryTemplateExistingMeasure).where(
                HazardLibraryTemplateExistingMeasure.template_assessment_id
                == assessment_id,
            ),
        ).all()
        known = {
            normalize_template_measure_description(row.description or "")
            for row in existing
            if (row.description or "").strip()
        }
        added = 0
        for measure in measures or ():
            description = (measure.description or "").strip()
            if not description:
                continue
            key = normalize_template_measure_description(description)
            if key in known:
                continue
            known.add(key)
            session.add(
                HazardLibraryTemplateExistingMeasure(
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                    sort_order=self._order._next_existing_measure_sort_order(
                        session,
                        assessment_id,
                    ),
                ),
            )
            added += 1
        return added

    def _add_unique_required_measures(self, session, *, assessment_id: int, measures) -> int:
        existing = session.scalars(
            select(HazardLibraryTemplateRequiredMeasure).where(
                HazardLibraryTemplateRequiredMeasure.template_assessment_id
                == assessment_id,
            ),
        ).all()
        known = {
            normalize_template_measure_description(row.description or "")
            for row in existing
            if (row.description or "").strip()
        }
        added = 0
        for measure in measures or ():
            description = (measure.description or "").strip()
            if not description:
                continue
            key = normalize_template_measure_description(description)
            if key in known:
                continue
            known.add(key)
            session.add(
                HazardLibraryTemplateRequiredMeasure(
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                    sort_order=self._order._next_required_measure_sort_order(
                        session,
                        assessment_id,
                    ),
                ),
            )
            added += 1
        return added

    def _find_active_assessments_containing_group(
        self,
        session,
        *,
        template_event_id: int,
        group_id: int,
    ) -> list[HazardLibraryTemplateAssessment]:
        assessments = list(
            session.scalars(
                select(HazardLibraryTemplateAssessment).where(
                    HazardLibraryTemplateAssessment.template_event_id
                    == template_event_id,
                    HazardLibraryTemplateAssessment.active.is_(True),
                ),
            ),
        )
        matches: list[HazardLibraryTemplateAssessment] = []
        for assessment in assessments:
            if group_id in self._assessment_group_ids(session, assessment):
                matches.append(assessment)
        return matches

    def _assessment_group_ids(
        self,
        session,
        assessment: HazardLibraryTemplateAssessment,
    ) -> set[int]:
        join_ids = session.scalars(
            select(HazardLibraryTemplateAssessmentExposedGroup.exposed_group_id).where(
                HazardLibraryTemplateAssessmentExposedGroup.assessment_id
                == assessment.id,
            ),
        ).all()
        ids = {int(value) for value in join_ids}
        if not ids and assessment.exposed_group_id:
            ids = {int(assessment.exposed_group_id)}
        return ids

    def _to_ambiguous_candidate(
        self,
        session,
        assessment: HazardLibraryTemplateAssessment,
    ) -> AmbiguousAssessmentCandidate:
        group_ids = sorted(self._assessment_group_ids(session, assessment))
        names = [
            exposed_group_service.display_name(group_id) or f"#{group_id}"
            for group_id in group_ids
        ]
        return AmbiguousAssessmentCandidate(
            assessment_id=int(assessment.id),
            severity=assessment.severity or "",
            severity_label=format_risk_severity_label(assessment.severity or ""),
            conclusion=(assessment.conclusion or "").strip(),
            group_names=", ".join(names) if names else "—",
        )

    def _create_assessment(
        self,
        session,
        *,
        template_event_id: int,
        assessment,
        package_reasoning: str,
        group_ids: list[int] | None = None,
    ) -> int:
        resolved_group_ids = group_ids or self._resolve_exposed_group_ids(assessment)
        if not resolved_group_ids:
            raise HazardCatalogPackageIncorporateError(
                CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP.format(
                    name=assessment.exposed_group or "posouzení",
                ),
            )
        severity = (
            assessment.severity
            if assessment.severity in RISK_SEVERITIES
            else DEFAULT_RISK_SEVERITY
        )
        row = HazardLibraryTemplateAssessment(
            template_event_id=template_event_id,
            exposed_group_id=resolved_group_ids[0],
            severity=severity,
            conclusion=(assessment.conclusion or "").strip(),
            note=(package_reasoning or "").strip(),
            active=True,
            sort_order=self._order._next_assessment_sort_order(session, template_event_id),
        )
        session.add(row)
        session.flush()

        for sort_order, group_id in enumerate(
            dict.fromkeys(resolved_group_ids),
            start=1,
        ):
            session.add(
                HazardLibraryTemplateAssessmentExposedGroup(
                    assessment_id=int(row.id),
                    exposed_group_id=group_id,
                    sort_order=sort_order,
                ),
            )
        return int(row.id)

    def _resolve_exposed_group_ids(self, assessment) -> list[int]:
        ids: list[int] = []
        seen: set[int] = set()
        candidate_ids = list(getattr(assessment, "exposed_group_ids", ()) or ())
        if assessment.exposed_group_id is not None:
            candidate_ids.insert(0, int(assessment.exposed_group_id))
        for group_id in candidate_ids:
            if group_id in seen:
                continue
            seen.add(int(group_id))
            ids.append(int(group_id))

        names = list(getattr(assessment, "exposed_groups", ()) or ())
        primary = (assessment.exposed_group or "").strip()
        if primary and primary not in names:
            names.insert(0, primary)
        for name in names:
            match = exposed_group_service.classify_name(name)
            if match.kind == ExposedGroupMatchKind.ACTIVE and match.groups:
                group_id = int(match.groups[0].id)
                if group_id not in seen:
                    seen.add(group_id)
                    ids.append(group_id)
        if not ids:
            raise HazardCatalogPackageIncorporateError(
                CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP.format(
                    name=assessment.exposed_group or "posouzení",
                ),
            )
        return ids

    def _resolve_exposed_group_id(self, assessment) -> int:
        return self._resolve_exposed_group_ids(assessment)[0]

    def _resolve_legal_document_id(self, link) -> int:
        if link.legal_document_id is not None:
            return int(link.legal_document_id)
        match = hazard_catalog_legal_document_resolver.resolve(link.reference or "")
        if match.kind == LegalDocumentMatchKind.EXACT and match.document_id is not None:
            return int(match.document_id)
        if match.kind == LegalDocumentMatchKind.AMBIGUOUS:
            raise HazardCatalogPackageIncorporateError(
                f"Právní odkaz „{link.reference}“ odpovídá více předpisům. "
                "Upravte balík a vyberte konkrétní předpis.",
            )
        raise HazardCatalogPackageIncorporateError(
            f"Právní odkaz „{link.reference}“ nebyl v registru předpisů nalezen. "
            "Upravte balík a vyberte existující právní předpis.",
        )

    @staticmethod
    def _stricter_severity(left: str, right: str) -> str:
        order = {severity: index for index, severity in enumerate(RISK_SEVERITIES)}
        left_rank = order.get(left, -1)
        right_rank = order.get(right, -1)
        return left if left_rank >= right_rank else right

    @staticmethod
    def _normalize_conclusion(text: str) -> str:
        return " ".join((text or "").strip().split()).casefold()

    @classmethod
    def _merge_conclusions(cls, existing: str, proposed: str) -> str:
        existing_text = (existing or "").strip()
        proposed_text = (proposed or "").strip()
        if not proposed_text:
            return existing_text
        if not existing_text:
            return proposed_text
        if cls._normalize_conclusion(existing_text) == cls._normalize_conclusion(
            proposed_text,
        ):
            return existing_text
        for paragraph in existing_text.split("\n\n"):
            if cls._normalize_conclusion(paragraph) == cls._normalize_conclusion(
                proposed_text,
            ):
                return existing_text
        return f"{existing_text}\n\n{proposed_text}"

    @staticmethod
    def _build_legal_note(link, package_reasoning: str) -> str:
        return HazardCatalogPackageIncorporateService._join_notes(
            link.reasoning,
            package_reasoning,
        )

    @staticmethod
    def _join_notes(*parts: str) -> str:
        return "\n".join(part.strip() for part in parts if (part or "").strip())

    def incorporate_package_into_working_copy(
        self,
        working_copy,
        *,
        template_id: int,
        package_record_id: int,
        group_assessment_overrides: dict[int, int] | None = None,
    ) -> CatalogPackageIncorporateResult:
        """Zapracuje balík pouze do pracovní kopie; stav balíku až při Uložit."""
        from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
            WcLegalLink,
        )

        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_MISSING)
        if not template.active:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE)

        record = self.package_repository.get_by_id(package_record_id)
        if record is None:
            raise HazardCatalogPackageIncorporateError("Návrhový balík neexistuje.")
        if record.status != PACKAGE_STATUS_PENDING:
            raise HazardCatalogPackageIncorporateError(
                "Zapracovat lze pouze balík čekající na odborné posouzení.",
            )
        if record.source_id != template_id:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH)
        if package_record_id in working_copy.pending_package_ids:
            raise HazardCatalogPackageIncorporateError(
                "Tento balík je již zapracován v pracovní kopii. Uložte změny.",
            )

        review = self.review_repository.get_by_id(record.ai_peer_review_id)
        if review is None:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISSING)
        if review.source_id != template_id:
            raise HazardCatalogPackageIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH)

        package = self.package_repository.package_from_record(record)
        export_id_map = self.get_export_id_map(record.ai_peer_review_id)
        overrides = {
            int(group_id): int(assessment_id)
            for group_id, assessment_id in (group_assessment_overrides or {}).items()
        }

        event_count = 0
        assessment_count = 0
        merged_assessment_count = 0
        existing_measure_count = 0
        required_measure_count = 0
        legal_link_count = 0

        event_id = self._wc_resolve_or_create_event(
            working_copy,
            package=package,
            export_id_map=export_id_map,
        )
        if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
            event_count = 1

        for assessment in package.assessments:
            created, merged, existing_added, required_added = self._wc_incorporate_assessment(
                working_copy,
                template_event_id=event_id,
                assessment=assessment,
                package_reasoning=package.reasoning,
                group_assessment_overrides=overrides,
            )
            assessment_count += created
            merged_assessment_count += merged
            existing_measure_count += existing_added
            required_measure_count += required_added

        for link in package.legal_links:
            document_id = self._resolve_legal_document_id(link)
            sort_order = max((row.sort_order for row in working_copy.legal_links), default=0) + 1
            working_copy.legal_links.append(
                WcLegalLink(
                    id=working_copy._alloc_id(),
                    template_id=template_id,
                    legal_document_id=document_id,
                    legal_requirement_id=None,
                    note=self._build_legal_note(link, package.reasoning),
                    active=True,
                    sort_order=sort_order,
                ),
            )
            working_copy._touch()
            legal_link_count += 1

        working_copy.queue_package_incorporate(package_record_id)
        return CatalogPackageIncorporateResult(
            package_record_id=package_record_id,
            new_revision_number=0,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
            legal_link_count=legal_link_count,
            merged_assessment_count=merged_assessment_count,
        )

    def _wc_resolve_or_create_event(self, working_copy, *, package, export_id_map) -> int:
        if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
            export_id = (package.target_event_export_id or "").strip()
            parent = export_id_map.get(export_id) if export_id else None
            if not isinstance(parent, dict) or parent.get("kind") != "event":
                raise HazardCatalogPackageIncorporateError(
                    CATALOG_INCORPORATE_ERROR_EVENT_PARENT.format(
                        name=package.event_name,
                    ),
                )
            event_id = int(parent["id"])
            if working_copy.get_event(event_id) is None:
                raise HazardCatalogPackageIncorporateError(
                    CATALOG_INCORPORATE_ERROR_EVENT_PARENT.format(
                        name=package.event_name,
                    ),
                )
            return event_id

        if package.package_type != AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
            raise HazardCatalogPackageIncorporateError(
                f"Nepodporovaný typ balíku „{package.package_type}“.",
            )
        if package.event is None or not package.event.name.strip():
            raise HazardCatalogPackageIncorporateError(
                "Balík typu nová událost musí obsahovat název události.",
            )
        event = working_copy.create_event(
            template_id=working_copy.template_id,
            name=package.event.name.strip(),
            description=(package.event.description or "").strip(),
            note=self._join_notes(package.event.note, package.reasoning),
            active=True,
        )
        return int(event.id)

    def _wc_incorporate_assessment(
        self,
        working_copy,
        *,
        template_event_id: int,
        assessment,
        package_reasoning: str,
        group_assessment_overrides: dict[int, int],
    ) -> tuple[int, int, int, int]:
        group_ids = self._resolve_exposed_group_ids(assessment)
        merge_targets = {}
        new_group_ids: list[int] = []

        for group_id in group_ids:
            matches = self._wc_find_active_assessments_containing_group(
                working_copy,
                template_event_id=template_event_id,
                group_id=group_id,
            )
            override_id = group_assessment_overrides.get(group_id)
            if override_id is not None:
                override = working_copy.get_assessment(override_id)
                if (
                    override is None
                    or not override.active
                    or int(override.template_event_id) != int(template_event_id)
                ):
                    raise HazardCatalogPackageIncorporateError(
                        "Vybrané cílové posouzení pro ohroženou skupinu není platné.",
                    )
                matches = [override]

            if len(matches) > 1:
                group_name = (
                    exposed_group_service.display_name(group_id) or f"#{group_id}"
                )
                raise HazardCatalogPackageAmbiguousGroupError(
                    group_id=group_id,
                    group_name=group_name,
                    candidates=tuple(
                        self._wc_to_ambiguous_candidate(row) for row in matches
                    ),
                )
            if len(matches) == 1:
                merge_targets[int(matches[0].id)] = matches[0]
            else:
                new_group_ids.append(group_id)

        existing_added = 0
        required_added = 0
        merged_count = 0

        for target in merge_targets.values():
            added_existing, added_required = self._wc_merge_into_assessment(
                working_copy,
                target=target,
                assessment=assessment,
                package_reasoning=package_reasoning,
            )
            existing_added += added_existing
            required_added += added_required
            merged_count += 1

        created_count = 0
        if new_group_ids:
            created = working_copy.create_assessment(
                template_id=working_copy.template_id,
                template_event_id=template_event_id,
                exposed_group_ids=new_group_ids,
                severity=(
                    assessment.severity
                    if assessment.severity in RISK_SEVERITIES
                    else DEFAULT_RISK_SEVERITY
                ),
                conclusion=(assessment.conclusion or "").strip(),
                note=(package_reasoning or "").strip(),
                active=True,
            )
            created_count = 1
            assessment_id = int(created.id)
            for measure in assessment.existing_measures:
                description = (measure.description or "").strip()
                if not description:
                    continue
                working_copy.create_existing_measure(
                    template_id=working_copy.template_id,
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                )
                existing_added += 1
            for measure in assessment.required_measures:
                description = (measure.description or "").strip()
                if not description:
                    continue
                working_copy.create_required_measure(
                    template_id=working_copy.template_id,
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                )
                required_added += 1

        return created_count, merged_count, existing_added, required_added

    def _wc_find_active_assessments_containing_group(
        self,
        working_copy,
        *,
        template_event_id: int,
        group_id: int,
    ):
        event = working_copy.get_event(template_event_id)
        if event is None:
            return []
        matches = []
        for assessment in event.assessments:
            if not assessment.active:
                continue
            if group_id in assessment.exposed_group_ids:
                matches.append(assessment)
        return matches

    def _wc_to_ambiguous_candidate(self, assessment) -> AmbiguousAssessmentCandidate:
        group_ids = sorted(assessment.exposed_group_ids)
        names = [
            exposed_group_service.display_name(group_id) or f"#{group_id}"
            for group_id in group_ids
        ]
        return AmbiguousAssessmentCandidate(
            assessment_id=int(assessment.id),
            severity=assessment.severity or "",
            severity_label=format_risk_severity_label(assessment.severity or ""),
            conclusion=(assessment.conclusion or "").strip(),
            group_names=", ".join(names) if names else "—",
        )

    def _wc_merge_into_assessment(
        self,
        working_copy,
        *,
        target,
        assessment,
        package_reasoning: str,
    ) -> tuple[int, int]:
        proposed_severity = (
            assessment.severity
            if assessment.severity in RISK_SEVERITIES
            else DEFAULT_RISK_SEVERITY
        )
        target.severity = self._stricter_severity(target.severity, proposed_severity)
        target.conclusion = self._merge_conclusions(
            target.conclusion or "",
            assessment.conclusion or "",
        )
        if package_reasoning.strip() and not (target.note or "").strip():
            target.note = package_reasoning.strip()
        working_copy._touch()

        existing_added = self._wc_add_unique_measures(
            working_copy,
            assessment_id=int(target.id),
            measures=assessment.existing_measures,
            existing=True,
        )
        required_added = self._wc_add_unique_measures(
            working_copy,
            assessment_id=int(target.id),
            measures=assessment.required_measures,
            existing=False,
        )
        return existing_added, required_added

    def _wc_add_unique_measures(
        self,
        working_copy,
        *,
        assessment_id: int,
        measures,
        existing: bool,
    ) -> int:
        bucket = (
            working_copy.get_existing_measures(assessment_id, include_inactive=True)
            if existing
            else working_copy.get_required_measures(assessment_id, include_inactive=True)
        )
        known = {
            normalize_template_measure_description(row.description or "")
            for row in bucket
            if (row.description or "").strip()
        }
        added = 0
        for measure in measures or ():
            description = (measure.description or "").strip()
            if not description:
                continue
            key = normalize_template_measure_description(description)
            if key in known:
                continue
            known.add(key)
            if existing:
                working_copy.create_existing_measure(
                    template_id=working_copy.template_id,
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                )
            else:
                working_copy.create_required_measure(
                    template_id=working_copy.template_id,
                    template_assessment_id=assessment_id,
                    description=description,
                    note=(measure.note or "").strip(),
                    active=True,
                )
            added += 1
        return added

    def _refresh_review_counts(self, review_id: int) -> None:
        packages = self.package_repository.get_for_review(review_id)
        review = self.review_repository.get_by_id(review_id)
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
        self.review_repository.update(review)


hazard_catalog_package_incorporate_service = HazardCatalogPackageIncorporateService()
