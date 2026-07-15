"""Zapracování návrhových balíků AI do MASTER katalogu (R20b)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

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
from moduly.rizeni_rizik.constants import DEFAULT_RISK_SEVERITY, RISK_SEVERITIES
from moduly.rizeni_rizik.constants_library import (
    CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP,
    CATALOG_INCORPORATE_ERROR_EVENT_PARENT,
    CATALOG_INCORPORATE_ERROR_GENERIC,
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
    LegalRequirementMatchKind,
    hazard_catalog_legal_requirement_resolver,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
    HazardCatalogProposalIncorporateService,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardCatalogPackageIncorporateError(ValueError):
    pass


@dataclass
class CatalogPackageIncorporateResult:
    package_record_id: int
    new_revision_number: int
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int
    legal_link_count: int


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

        event_count = 0
        assessment_count = 0
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
                assessment_id = self._create_assessment(
                    session,
                    template_event_id=event_id,
                    assessment=assessment,
                    package_reasoning=package.reasoning,
                )
                assessment_count += 1
                for measure in assessment.existing_measures:
                    session.add(
                        HazardLibraryTemplateExistingMeasure(
                            template_assessment_id=assessment_id,
                            description=(measure.description or "").strip(),
                            note=(measure.note or "").strip(),
                            active=True,
                            sort_order=self._order._next_existing_measure_sort_order(
                                session,
                                assessment_id,
                            ),
                        ),
                    )
                    existing_measure_count += 1
                for measure in assessment.required_measures:
                    session.add(
                        HazardLibraryTemplateRequiredMeasure(
                            template_assessment_id=assessment_id,
                            description=(measure.description or "").strip(),
                            note=(measure.note or "").strip(),
                            active=True,
                            sort_order=self._order._next_required_measure_sort_order(
                                session,
                                assessment_id,
                            ),
                        ),
                    )
                    required_measure_count += 1

            for link in package.legal_links:
                requirement_id = self._resolve_legal_requirement_id(link)
                session.add(
                    HazardLibraryTemplateLegalLink(
                        template_id=template_id,
                        legal_requirement_id=requirement_id,
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

    def _create_assessment(
        self,
        session,
        *,
        template_event_id: int,
        assessment,
        package_reasoning: str,
    ) -> int:
        group_id = self._resolve_exposed_group_id(assessment)
        severity = (
            assessment.severity
            if assessment.severity in RISK_SEVERITIES
            else DEFAULT_RISK_SEVERITY
        )
        consequence = (assessment.consequence or "").strip()
        if not consequence:
            raise HazardCatalogPackageIncorporateError(
                CATALOG_INCORPORATE_ERROR_GENERIC.format(
                    name=assessment.exposed_group or "posouzení",
                ),
            )
        row = HazardLibraryTemplateAssessment(
            template_event_id=template_event_id,
            exposed_group_id=group_id,
            consequence=consequence,
            severity=severity,
            conclusion=(assessment.conclusion or "").strip(),
            note=(package_reasoning or "").strip(),
            active=True,
            sort_order=self._order._next_assessment_sort_order(session, template_event_id),
        )
        session.add(row)
        session.flush()
        return int(row.id)

    def _resolve_exposed_group_id(self, assessment) -> int:
        if assessment.exposed_group_id is not None:
            return int(assessment.exposed_group_id)
        match = exposed_group_service.classify_name(assessment.exposed_group or "")
        if match.kind == ExposedGroupMatchKind.ACTIVE and match.groups:
            return int(match.groups[0].id)
        raise HazardCatalogPackageIncorporateError(
            CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP.format(
                name=assessment.exposed_group or "posouzení",
            ),
        )

    def _resolve_legal_requirement_id(self, link) -> int:
        if link.legal_requirement_id is not None:
            return int(link.legal_requirement_id)
        match = hazard_catalog_legal_requirement_resolver.resolve(link.reference or "")
        if match.kind == LegalRequirementMatchKind.EXACT and match.requirement_id is not None:
            return int(match.requirement_id)
        if match.kind == LegalRequirementMatchKind.AMBIGUOUS:
            raise HazardCatalogPackageIncorporateError(
                f"Právní odkaz „{link.reference}“ odpovídá více požadavkům. "
                "Upravte balík a vyberte konkrétní požadavek.",
            )
        raise HazardCatalogPackageIncorporateError(
            f"Právní odkaz „{link.reference}“ nebyl v registru nalezen. "
            "Upravte balík a vyberte existující právní požadavek.",
        )

    @staticmethod
    def _build_legal_note(link, package_reasoning: str) -> str:
        return HazardCatalogPackageIncorporateService._join_notes(
            link.reasoning,
            package_reasoning,
        )

    @staticmethod
    def _join_notes(*parts: str) -> str:
        return "\n".join(part.strip() for part in parts if (part or "").strip())

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
