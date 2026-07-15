"""Zapracování návrhů AI do MASTER obsahu katalogu zdrojů rizik (R18g, R19)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from core.ai_oponentni.modely.ai_unassigned_proposal import (
    PROPOSAL_STATUS_INCORPORATED,
    PROPOSAL_STATUS_PENDING,
    PROPOSAL_STATUS_REJECTED,
    PROPOSAL_STATUS_UNASSIGNED,
    AiUnassignedProposal,
)
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.database.session import get_session
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_LABELS,
)
from moduly.rizeni_rizik.constants_library import (
    CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP,
    CATALOG_INCORPORATE_ERROR_ASSESSMENT_PARENT,
    CATALOG_INCORPORATE_ERROR_EVENT_PARENT,
    CATALOG_INCORPORATE_ERROR_EXPOSED_GROUP,
    CATALOG_INCORPORATE_ERROR_GENERIC,
    CATALOG_INCORPORATE_ERROR_MEASURE_PARENT,
    CATALOG_INCORPORATE_ERROR_NO_PENDING,
    CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH,
    CATALOG_INCORPORATE_ERROR_REVIEW_MISSING,
    CATALOG_INCORPORATE_ERROR_SELECT_PROPOSALS,
    CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE,
    CATALOG_INCORPORATE_ERROR_SOURCE_MISSING,
    CATALOG_INCORPORATE_ERROR_UNKNOWN_AREA,
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
    LegalDocumentMatchKind,
    hazard_catalog_legal_document_resolver,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
    CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE,
    CATALOG_CONFLICT_TYPE_DUPLICATE,
    CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE,
    CATALOG_DUPLICATE_ACTION_MERGE,
    CATALOG_DUPLICATE_ACTION_SKIP,
    CATALOG_DUPLICATE_MATCH_EXACT,
    CATALOG_DUPLICATE_MATCH_SIMILAR,
    CATALOG_PROPOSAL_KIND_ASSESSMENT,
    CATALOG_PROPOSAL_KIND_EVENT,
    CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
    CATALOG_PROPOSAL_KIND_EXPOSED_GROUP,
    CATALOG_PROPOSAL_KIND_LEGAL,
    CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
    CATALOG_PROPOSAL_KIND_UNKNOWN,
    CatalogAssessmentCandidate,
    CatalogIncorporatePlan,
    CatalogProposalConflict,
    CatalogProposalDuplicate,
    CatalogProposalPayload,
    area_matches,
    classify_catalog_proposal,
    is_exact_text_match,
    is_similar_text_match,
    normalize_match_text,
    parse_proposal_payload,
    proposal_payload_to_json,
    requires_dialog_for_duplicate,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardCatalogProposalIncorporateError(ValueError):
    pass


@dataclass
class CatalogIncorporateResult:
    incorporated_count: int
    newly_incorporated_count: int
    used_existing_count: int
    skipped_count: int
    requires_manual_decision_count: int
    manual_decision_proposal_ids: list[int]
    merged_count: int
    new_revision_number: int | None


@dataclass
class CatalogProposalResolution:
    proposal_id: int
    action: str


class HazardCatalogProposalIncorporateService:
    def __init__(self):
        self.proposal_repository = AiUnassignedProposalRepository()
        self.review_repository = AiPeerReviewRepository()

    def get_export_id_map(self, review_id: int) -> dict[str, dict]:
        review = self.review_repository.get_by_id(review_id)
        if review is None:
            return {}
        try:
            export_id_map = json.loads(review.export_id_map_json or "{}")
        except json.JSONDecodeError:
            export_id_map = {}
        return export_id_map if isinstance(export_id_map, dict) else {}

    def detect_duplicate(
        self,
        *,
        template_id: int,
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> CatalogProposalDuplicate | None:
        duplicate = self._find_duplicate_match(
            template_id=template_id,
            proposal=proposal,
            export_id_map=export_id_map,
        )
        if duplicate is None or duplicate.match_type != CATALOG_DUPLICATE_MATCH_EXACT:
            return None
        return duplicate

    def prepare_incorporation(
        self,
        *,
        template_id: int,
        review_id: int,
        proposal_ids: list[int],
    ) -> CatalogIncorporatePlan:
        export_id_map = self.get_export_id_map(review_id)
        proposals = [
            proposal
            for proposal in self.proposal_repository.get_by_ids(proposal_ids)
            if proposal.status == PROPOSAL_STATUS_PENDING
        ]
        resolutions: dict[int, str] = {}
        conflicts: list[CatalogProposalConflict] = []
        pending_proposal_ids: list[int] = []

        for proposal in proposals:
            working = self.proposal_repository.get_by_id(proposal.id)
            if working is None or working.status != PROPOSAL_STATUS_PENDING:
                continue

            if self.auto_resolve_codebooks(working):
                self.proposal_repository.update(working)

            kind = classify_catalog_proposal(working)
            if kind == CATALOG_PROPOSAL_KIND_LEGAL:
                if self._prepare_legal_proposal(
                    working,
                    template_id=template_id,
                    resolutions=resolutions,
                    conflicts=conflicts,
                    pending_proposal_ids=pending_proposal_ids,
                ):
                    continue

            if kind in {
                CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
                CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
            } and self._needs_assessment_choice(working, export_id_map):
                candidates = self._list_suitable_assessment_candidates(
                    template_id,
                    review_id,
                    working,
                    export_id_map,
                )
                if len(candidates) == 1:
                    self.assign_proposal_assessment(working.id, candidates[0].export_id)
                    working = self.proposal_repository.get_by_id(working.id)
                    if working is None or working.status != PROPOSAL_STATUS_PENDING:
                        continue
                elif len(candidates) > 1:
                    conflicts.append(
                        CatalogProposalConflict(
                            proposal_id=working.id,
                            proposal_label=working.name,
                            conflict_type=CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
                            assessment_candidates=candidates,
                        ),
                    )
                    continue
                else:
                    conflicts.append(
                        CatalogProposalConflict(
                            proposal_id=working.id,
                            proposal_label=working.name,
                            conflict_type=CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE,
                            template_event_choices=self._list_template_event_choices(template_id),
                        ),
                    )
                    continue

            duplicate = self._find_duplicate_match(
                template_id=template_id,
                proposal=working,
                export_id_map=export_id_map,
            )
            if duplicate is None:
                continue
            if duplicate.match_type == CATALOG_DUPLICATE_MATCH_EXACT:
                resolutions[working.id] = CATALOG_DUPLICATE_ACTION_MERGE
                continue
            if requires_dialog_for_duplicate(duplicate):
                conflicts.append(
                    CatalogProposalConflict(
                        proposal_id=working.id,
                        proposal_label=working.name,
                        conflict_type=CATALOG_CONFLICT_TYPE_DUPLICATE,
                        duplicate=duplicate,
                    ),
                )
        return CatalogIncorporatePlan(
            resolutions=resolutions,
            conflicts=conflicts,
            pending_proposal_ids=pending_proposal_ids,
        )

    def auto_resolve_codebooks(self, proposal: AiUnassignedProposal) -> bool:
        changed = False
        if self._auto_resolve_exposed_group(proposal):
            changed = True
        if self._auto_resolve_severity(proposal):
            changed = True
        return changed

    def _auto_resolve_exposed_group(self, proposal: AiUnassignedProposal) -> bool:
        if proposal.exposed_group_id is not None:
            return False

        from moduly.nastaveni.sluzby.exposed_group_service import (
            ExposedGroupMatchKind,
            exposed_group_service,
        )

        kind = classify_catalog_proposal(proposal)
        candidates: list[str] = []
        if kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            candidates.append(proposal.name)
        elif kind == CATALOG_PROPOSAL_KIND_ASSESSMENT and area_matches(
            (proposal.area or "").casefold(),
            ("ohrožen", "ohrozen", "skupin"),
        ):
            candidates.append(proposal.name)

        for candidate in candidates:
            match = exposed_group_service.classify_name(candidate)
            if match.kind == ExposedGroupMatchKind.ACTIVE and match.groups:
                proposal.exposed_group_id = match.groups[0].id
                return True
        return False

    def _auto_resolve_severity(self, proposal: AiUnassignedProposal) -> bool:
        if classify_catalog_proposal(proposal) != CATALOG_PROPOSAL_KIND_ASSESSMENT:
            return False

        payload = parse_proposal_payload(proposal)
        if payload.severity in RISK_SEVERITIES:
            return False

        resolved = self._resolve_severity_value(
            payload.severity,
            proposal.name,
            proposal.reasoning,
        )
        if resolved == payload.severity or resolved not in RISK_SEVERITIES:
            return False

        proposal.payload_json = proposal_payload_to_json(
            CatalogProposalPayload(
                description=payload.description,
                note=payload.note,
                consequence=payload.consequence,
                conclusion=payload.conclusion,
                severity=resolved,
            ),
        )
        return True

    @staticmethod
    def _resolve_severity_value(*candidates: str) -> str:
        for candidate in candidates:
            normalized = normalize_match_text(candidate)
            if not normalized:
                continue
            if candidate in RISK_SEVERITIES:
                return candidate
            for severity, label in RISK_SEVERITY_LABELS.items():
                if normalize_match_text(label) == normalized:
                    return severity
        return ""

    def _prepare_legal_proposal(
        self,
        proposal: AiUnassignedProposal,
        *,
        template_id: int,
        resolutions: dict[int, str],
        conflicts: list[CatalogProposalConflict],
        pending_proposal_ids: list[int],
    ) -> bool:
        payload = parse_proposal_payload(proposal)
        requirement_id = payload.legal_requirement_id
        document_id = payload.legal_document_id
        if document_id is None and requirement_id is not None:
            from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
                legal_requirement_service,
            )

            requirement = legal_requirement_service.get_by_id(requirement_id)
            if requirement is not None and requirement.legal_document_id is not None:
                document_id = int(requirement.legal_document_id)
                self._store_legal_document_id(proposal, document_id)
                self.proposal_repository.update(proposal)

        if document_id is None:
            match = hazard_catalog_legal_document_resolver.resolve(proposal.name)
            if match.kind == LegalDocumentMatchKind.NONE:
                pending_proposal_ids.append(proposal.id)
                return True
            if match.kind == LegalDocumentMatchKind.AMBIGUOUS:
                conflicts.append(
                    CatalogProposalConflict(
                        proposal_id=proposal.id,
                        proposal_label=proposal.name,
                        conflict_type=CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE,
                        requirement_candidates=match.candidates,
                    ),
                )
                return True
            document_id = match.document_id
            self._store_legal_document_id(proposal, document_id)
            self.proposal_repository.update(proposal)

        duplicate = self._find_legal_link_duplicate(template_id, document_id)
        if duplicate is None:
            return True
        if duplicate.match_type == CATALOG_DUPLICATE_MATCH_EXACT:
            resolutions[proposal.id] = CATALOG_DUPLICATE_ACTION_MERGE
            return True
        if requires_dialog_for_duplicate(duplicate):
            conflicts.append(
                CatalogProposalConflict(
                    proposal_id=proposal.id,
                    proposal_label=proposal.name,
                    conflict_type=CATALOG_CONFLICT_TYPE_DUPLICATE,
                    duplicate=duplicate,
                ),
            )
        return True

    @staticmethod
    def _store_legal_document_id(
        proposal: AiUnassignedProposal,
        legal_document_id: int | None,
    ) -> None:
        payload = parse_proposal_payload(proposal)
        proposal.payload_json = proposal_payload_to_json(
            CatalogProposalPayload(
                description=payload.description,
                note=payload.note,
                consequence=payload.consequence,
                conclusion=payload.conclusion,
                severity=payload.severity,
                legal_document_id=legal_document_id,
                legal_requirement_id=payload.legal_requirement_id,
            ),
        )

    @staticmethod
    def _store_legal_requirement_id(
        proposal: AiUnassignedProposal,
        legal_requirement_id: int | None,
    ) -> None:
        payload = parse_proposal_payload(proposal)
        proposal.payload_json = proposal_payload_to_json(
            CatalogProposalPayload(
                description=payload.description,
                note=payload.note,
                consequence=payload.consequence,
                conclusion=payload.conclusion,
                severity=payload.severity,
                legal_document_id=payload.legal_document_id,
                legal_requirement_id=legal_requirement_id,
            ),
        )

    @staticmethod
    def _needs_assessment_choice(
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> bool:
        parent = HazardCatalogProposalIncorporateService._resolve_parent(
            proposal,
            export_id_map,
        )
        return parent is None or parent.get("kind") != "assessment"

    def _list_suitable_assessment_candidates(
        self,
        template_id: int,
        review_id: int,
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> tuple[CatalogAssessmentCandidate, ...]:
        from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

        parent = self._resolve_parent(proposal, export_id_map)
        event_filter_id: int | None = None
        if parent is not None and parent.get("kind") == "event":
            event_filter_id = int(parent["id"])

        event_names: dict[int, str] = {}
        for event in self._active_events(template_id):
            event_names[event.id] = event.name

        export_id_by_assessment_id = {
            int(payload["id"]): export_id
            for export_id, payload in export_id_map.items()
            if payload.get("kind") == "assessment" and payload.get("id") is not None
        }

        candidates: list[CatalogAssessmentCandidate] = []
        for event in self._active_events(template_id):
            if event_filter_id is not None and event.id != event_filter_id:
                continue
            for assessment in self._active_assessments(event.id):
                export_id = export_id_by_assessment_id.get(assessment.id)
                if export_id is None:
                    export_id = self.ensure_assessment_export_id(review_id, assessment.id)
                group_name = exposed_group_service.display_name(assessment.exposed_group_id)
                candidates.append(
                    CatalogAssessmentCandidate(
                        export_id=export_id,
                        event_name=event_names.get(event.id, "Událost"),
                        group_name=group_name or "—",
                        assessment_id=assessment.id,
                        template_event_id=event.id,
                    ),
                )
        return tuple(candidates)

    @staticmethod
    def _list_template_event_choices(template_id: int) -> tuple[tuple[int, str], ...]:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
            hazard_library_template_event_service,
        )

        return tuple(
            (event.id, event.name)
            for event in hazard_library_template_event_service.get_for_template(
                template_id,
                include_inactive=False,
            )
        )

    def ensure_assessment_export_id(self, review_id: int, assessment_id: int) -> str:
        export_id_map = dict(self.get_export_id_map(review_id))
        for export_id, payload in export_id_map.items():
            if payload.get("kind") == "assessment" and payload.get("id") == assessment_id:
                return export_id

        counter = 0
        for export_id in export_id_map:
            if export_id.startswith("ASSESSMENT-"):
                try:
                    counter = max(counter, int(export_id.split("-", 1)[1]))
                except (IndexError, ValueError):
                    continue
        new_export_id = f"ASSESSMENT-{counter + 1:03d}"
        export_id_map[new_export_id] = {"kind": "assessment", "id": assessment_id}
        self._save_export_id_map(review_id, export_id_map)
        return new_export_id

    def _save_export_id_map(self, review_id: int, export_id_map: dict[str, dict]) -> None:
        review = self.review_repository.get_by_id(review_id)
        if review is None:
            return
        review.export_id_map_json = json.dumps(export_id_map, ensure_ascii=False)
        self.review_repository.update(review)

    def assign_proposal_assessment_by_id(
        self,
        proposal_id: int,
        review_id: int,
        assessment_id: int,
    ) -> None:
        export_id = self.ensure_assessment_export_id(review_id, assessment_id)
        self.assign_proposal_assessment(proposal_id, export_id)

    def _find_legal_link_duplicate(
        self,
        template_id: int,
        legal_document_id: int | None,
    ) -> CatalogProposalDuplicate | None:
        if legal_document_id is None:
            return None
        from moduly.pravni_pozadavky.constants import legal_document_catalog_link_label
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
            hazard_library_template_legal_link_service,
        )

        document = legal_document_service.get_by_id(legal_document_id)
        label = legal_document_catalog_link_label(document) if document else "—"
        for link in hazard_library_template_legal_link_service.get_for_template(
            template_id,
            include_inactive=False,
        ):
            if link.legal_document_id == legal_document_id:
                return CatalogProposalDuplicate(
                    kind=CATALOG_PROPOSAL_KIND_LEGAL,
                    match_type=CATALOG_DUPLICATE_MATCH_EXACT,
                    existing_label=label,
                    existing_id=link.id,
                    proposal_label=label,
                )
        return None

    def assign_proposal_assessment(
        self,
        proposal_id: int,
        assessment_export_id: str,
    ) -> None:
        proposal = self.proposal_repository.get_by_id(proposal_id)
        if proposal is None:
            return
        proposal.parent_export_id = assessment_export_id.strip()
        self.proposal_repository.update(proposal)

    def assign_proposal_legal_document(
        self,
        proposal_id: int,
        legal_document_id: int,
    ) -> None:
        proposal = self.proposal_repository.get_by_id(proposal_id)
        if proposal is None:
            return
        self._store_legal_document_id(proposal, legal_document_id)
        self.proposal_repository.update(proposal)

    def assign_proposal_legal_requirement(
        self,
        proposal_id: int,
        legal_requirement_id: int,
    ) -> None:
        """Deprecated alias — ID se bere jako legal_document_id (R19b)."""
        self.assign_proposal_legal_document(proposal_id, legal_requirement_id)

    def _find_duplicate_match(
        self,
        *,
        template_id: int,
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> CatalogProposalDuplicate | None:
        kind = classify_catalog_proposal(proposal)
        payload = parse_proposal_payload(proposal)

        if kind == CATALOG_PROPOSAL_KIND_EVENT:
            return self._match_content_duplicate(
                kind=kind,
                proposal_label=proposal.name,
                candidates=[
                    (event.name, event.id)
                    for event in self._active_events(template_id)
                ],
            )

        if kind == CATALOG_PROPOSAL_KIND_ASSESSMENT:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "event":
                return None
            if proposal.exposed_group_id is None:
                return None
            for assessment in self._active_assessments(int(parent["id"])):
                if assessment.exposed_group_id != proposal.exposed_group_id:
                    continue
                from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

                group_name = exposed_group_service.display_name(assessment.exposed_group_id)
                return CatalogProposalDuplicate(
                    kind=kind,
                    match_type=CATALOG_DUPLICATE_MATCH_EXACT,
                    existing_label=group_name or "—",
                    existing_id=assessment.id,
                    proposal_label=proposal.name,
                )
            return None

        if kind in {
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
        }:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "assessment":
                return None
            description = payload.description or proposal.name
            measures = (
                self._active_existing_measures(int(parent["id"]))
                if kind == CATALOG_PROPOSAL_KIND_EXISTING_MEASURE
                else self._active_required_measures(int(parent["id"]))
            )
            return self._match_content_duplicate(
                kind=kind,
                proposal_label=description,
                candidates=[(measure.description, measure.id) for measure in measures],
            )

        if kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

            return self._match_codebook_duplicate(
                kind=kind,
                proposal_label=proposal.name,
                candidates=[
                    (group.name, group.id)
                    for group in exposed_group_service.get_all(include_inactive=False)
                ],
            )

        if kind == CATALOG_PROPOSAL_KIND_LEGAL:
            payload = parse_proposal_payload(proposal)
            return self._find_legal_link_duplicate(template_id, payload.legal_document_id)

        return None

    @staticmethod
    def _match_codebook_duplicate(
        *,
        kind: str,
        proposal_label: str,
        candidates: list[tuple[str, int | None]],
    ) -> CatalogProposalDuplicate | None:
        for existing_label, existing_id in candidates:
            if is_exact_text_match(proposal_label, existing_label):
                return CatalogProposalDuplicate(
                    kind=kind,
                    match_type=CATALOG_DUPLICATE_MATCH_EXACT,
                    existing_label=existing_label,
                    existing_id=existing_id,
                    proposal_label=proposal_label,
                )
        for existing_label, existing_id in candidates:
            if is_similar_text_match(proposal_label, existing_label):
                return CatalogProposalDuplicate(
                    kind=kind,
                    match_type=CATALOG_DUPLICATE_MATCH_SIMILAR,
                    existing_label=existing_label,
                    existing_id=existing_id,
                    proposal_label=proposal_label,
                )
        return None

    @staticmethod
    def _match_content_duplicate(
        *,
        kind: str,
        proposal_label: str,
        candidates: list[tuple[str, int | None]],
    ) -> CatalogProposalDuplicate | None:
        for existing_label, existing_id in candidates:
            if is_exact_text_match(proposal_label, existing_label):
                return CatalogProposalDuplicate(
                    kind=kind,
                    match_type=CATALOG_DUPLICATE_MATCH_EXACT,
                    existing_label=existing_label,
                    existing_id=existing_id,
                    proposal_label=proposal_label,
                )

        similar_candidates = [
            (existing_label, existing_id)
            for existing_label, existing_id in candidates
            if is_similar_text_match(proposal_label, existing_label)
        ]
        if not similar_candidates:
            return None
        existing_label, existing_id = similar_candidates[0]
        return CatalogProposalDuplicate(
            kind=kind,
            match_type=CATALOG_DUPLICATE_MATCH_SIMILAR,
            existing_label=existing_label,
            existing_id=existing_id,
            proposal_label=proposal_label,
        )

    def reject_proposals(self, proposal_ids: list[int]) -> int:
        if not proposal_ids:
            return 0
        review_ids: set[int] = set()
        with get_session() as session:
            rejected = 0
            for proposal_id in proposal_ids:
                proposal = session.get(AiUnassignedProposal, proposal_id)
                if proposal is None or proposal.status != PROPOSAL_STATUS_PENDING:
                    continue
                proposal.status = PROPOSAL_STATUS_REJECTED
                review_ids.add(proposal.ai_peer_review_id)
                rejected += 1
            session.commit()
        for review_id in review_ids:
            self._refresh_review_counts(review_id)
        return rejected

    def incorporate_proposals(
        self,
        *,
        template_id: int,
        review_id: int,
        proposal_ids: list[int],
        resolutions: dict[int, str],
        pending_proposal_ids: list[int] | None = None,
    ) -> CatalogIncorporateResult:
        if not proposal_ids:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_SELECT_PROPOSALS)

        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_MISSING)
        if not template.active:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_INACTIVE)

        review = self.review_repository.get_by_id(review_id)
        if review is None:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISSING)
        if review.source_id != template_id:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_REVIEW_MISMATCH)

        export_id_map = self.get_export_id_map(review_id)
        proposals = [
            proposal
            for proposal in self.proposal_repository.get_by_ids(proposal_ids)
            if proposal.status == PROPOSAL_STATUS_PENDING
        ]
        if not proposals:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_NO_PENDING)

        pending_ids = set(pending_proposal_ids or [])
        incorporated = 0
        newly_created = 0
        used_existing = 0
        skipped = 0
        requires_manual = 0
        manual_decision_proposal_ids: list[int] = []
        applied_any = False
        new_revision_number: int | None = None

        session = get_session()
        try:
            db_template = session.get(HazardLibraryTemplate, template_id)
            if db_template is None:
                raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_SOURCE_MISSING)

            for proposal in proposals:
                if proposal.id in pending_ids:
                    requires_manual += 1
                    manual_decision_proposal_ids.append(proposal.id)
                    continue

                action = resolutions.get(proposal.id, "")
                if action == CATALOG_DUPLICATE_ACTION_SKIP:
                    skipped += 1
                    continue

                db_proposal = session.get(AiUnassignedProposal, proposal.id)
                if db_proposal is None or db_proposal.status != PROPOSAL_STATUS_PENDING:
                    continue

                kind = classify_catalog_proposal(db_proposal)
                if kind == CATALOG_PROPOSAL_KIND_LEGAL:
                    payload = parse_proposal_payload(db_proposal)
                    if payload.legal_document_id is None and payload.legal_requirement_id is None:
                        requires_manual += 1
                        manual_decision_proposal_ids.append(proposal.id)
                        continue
                if kind == CATALOG_PROPOSAL_KIND_UNKNOWN:
                    raise HazardCatalogProposalIncorporateError(
                        CATALOG_INCORPORATE_ERROR_UNKNOWN_AREA.format(name=db_proposal.name),
                    )

                if action == CATALOG_DUPLICATE_ACTION_MERGE:
                    db_proposal.status = PROPOSAL_STATUS_INCORPORATED
                    used_existing += 1
                    incorporated += 1
                    applied_any = True
                    continue

                self._apply_proposal(
                    session,
                    template_id=template_id,
                    proposal=db_proposal,
                    export_id_map=export_id_map,
                )
                db_proposal.status = PROPOSAL_STATUS_INCORPORATED
                newly_created += 1
                incorporated += 1
                applied_any = True

            if applied_any:
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
        except HazardCatalogProposalIncorporateError:
            session.rollback()
            raise
        except Exception as error:
            session.rollback()
            raise HazardCatalogProposalIncorporateError(str(error)) from error
        finally:
            session.close()

        self._refresh_review_counts(review_id)
        return CatalogIncorporateResult(
            incorporated_count=incorporated,
            newly_incorporated_count=newly_created,
            used_existing_count=used_existing,
            skipped_count=skipped,
            requires_manual_decision_count=requires_manual,
            manual_decision_proposal_ids=manual_decision_proposal_ids,
            merged_count=used_existing,
            new_revision_number=new_revision_number,
        )

    @staticmethod
    def list_legal_document_candidates() -> tuple[tuple[int, str], ...]:
        from moduly.pravni_pozadavky.constants import legal_document_catalog_link_label
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )

        return tuple(
            (document.id, legal_document_catalog_link_label(document))
            for document in legal_document_service.list_all(include_inactive=False)
        )

    @staticmethod
    def list_legal_requirement_candidates() -> tuple[tuple[int, str], ...]:
        """Deprecated alias — kandidáti jsou právní předpisy (R19b)."""
        return HazardCatalogProposalIncorporateService.list_legal_document_candidates()

    def merge_incorporate_results(
        self,
        base: CatalogIncorporateResult,
        extra: CatalogIncorporateResult,
    ) -> CatalogIncorporateResult:
        revision = extra.new_revision_number or base.new_revision_number
        return CatalogIncorporateResult(
            incorporated_count=base.incorporated_count + extra.incorporated_count,
            newly_incorporated_count=base.newly_incorporated_count
            + extra.newly_incorporated_count,
            used_existing_count=base.used_existing_count + extra.used_existing_count,
            skipped_count=base.skipped_count + extra.skipped_count,
            requires_manual_decision_count=extra.requires_manual_decision_count,
            manual_decision_proposal_ids=list(extra.manual_decision_proposal_ids),
            merged_count=base.merged_count + extra.merged_count,
            new_revision_number=revision,
        )

    def incorporate_single_proposal(
        self,
        *,
        template_id: int,
        review_id: int,
        proposal_id: int,
        resolutions: dict[int, str] | None = None,
    ) -> CatalogIncorporateResult:
        plan = self.prepare_incorporation(
            template_id=template_id,
            review_id=review_id,
            proposal_ids=[proposal_id],
        )
        merged_resolutions = dict(plan.resolutions)
        if resolutions:
            merged_resolutions.update(resolutions)
        return self.incorporate_proposals(
            template_id=template_id,
            review_id=review_id,
            proposal_ids=[proposal_id],
            resolutions=merged_resolutions,
            pending_proposal_ids=[],
        )

    def _apply_proposal(
        self,
        session,
        *,
        template_id: int,
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> None:
        kind = classify_catalog_proposal(proposal)
        payload = parse_proposal_payload(proposal)
        note = self._build_note(proposal, payload)

        if kind == CATALOG_PROPOSAL_KIND_EVENT:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "source":
                raise HazardCatalogProposalIncorporateError(
                    CATALOG_INCORPORATE_ERROR_EVENT_PARENT.format(name=proposal.name),
                )
            event = HazardLibraryTemplateEvent(
                template_id=template_id,
                name=(proposal.name or "").strip(),
                description=(payload.description or proposal.reasoning or "").strip(),
                note=note,
                active=True,
                sort_order=self._next_event_sort_order(session, template_id),
            )
            session.add(event)
            return

        if kind == CATALOG_PROPOSAL_KIND_ASSESSMENT:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "event":
                raise HazardCatalogProposalIncorporateError(
                    CATALOG_INCORPORATE_ERROR_ASSESSMENT_PARENT.format(name=proposal.name),
                )
            if proposal.exposed_group_id is None:
                raise HazardCatalogProposalIncorporateError(
                    CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP.format(name=proposal.name),
                )
            severity = payload.severity if payload.severity in RISK_SEVERITIES else DEFAULT_RISK_SEVERITY
            consequence = (
                payload.consequence
                or proposal.name
                or proposal.reasoning
                or "Dle návrhu AI"
            ).strip()
            assessment = HazardLibraryTemplateAssessment(
                template_event_id=int(parent["id"]),
                exposed_group_id=proposal.exposed_group_id,
                consequence=consequence,
                severity=severity,
                conclusion=(payload.conclusion or "").strip(),
                note=note,
                active=True,
                sort_order=self._next_assessment_sort_order(session, int(parent["id"])),
            )
            session.add(assessment)
            return

        if kind == CATALOG_PROPOSAL_KIND_EXISTING_MEASURE:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "assessment":
                raise HazardCatalogProposalIncorporateError(
                    CATALOG_INCORPORATE_ERROR_MEASURE_PARENT.format(name=proposal.name),
                )
            measure = HazardLibraryTemplateExistingMeasure(
                template_assessment_id=int(parent["id"]),
                description=(payload.description or proposal.name or "").strip(),
                note=note,
                active=True,
                sort_order=self._next_existing_measure_sort_order(session, int(parent["id"])),
            )
            session.add(measure)
            return

        if kind == CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "assessment":
                raise HazardCatalogProposalIncorporateError(
                    CATALOG_INCORPORATE_ERROR_MEASURE_PARENT.format(name=proposal.name),
                )
            measure = HazardLibraryTemplateRequiredMeasure(
                template_assessment_id=int(parent["id"]),
                description=(payload.description or proposal.name or "").strip(),
                note=note,
                active=True,
                sort_order=self._next_required_measure_sort_order(session, int(parent["id"])),
            )
            session.add(measure)
            return

        if kind == CATALOG_PROPOSAL_KIND_LEGAL:
            document_id = payload.legal_document_id
            if document_id is None:
                return
            link = HazardLibraryTemplateLegalLink(
                template_id=template_id,
                legal_document_id=document_id,
                legal_requirement_id=payload.legal_requirement_id,
                note=note,
                active=True,
                sort_order=self._next_legal_link_sort_order(session, template_id),
            )
            session.add(link)
            return

        if kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            raise HazardCatalogProposalIncorporateError(CATALOG_INCORPORATE_ERROR_EXPOSED_GROUP)

        raise HazardCatalogProposalIncorporateError(
            CATALOG_INCORPORATE_ERROR_GENERIC.format(name=proposal.name),
        )

    @staticmethod
    def _build_note(proposal: AiUnassignedProposal, payload: CatalogProposalPayload) -> str:
        parts = [payload.note.strip(), (proposal.reasoning or "").strip()]
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _resolve_parent(
        proposal: AiUnassignedProposal,
        export_id_map: dict[str, dict],
    ) -> dict | None:
        parent_id = (proposal.parent_export_id or "").strip()
        if not parent_id:
            return None
        parent = export_id_map.get(parent_id)
        return parent if isinstance(parent, dict) else None

    def _refresh_review_counts(self, review_id: int) -> None:
        proposals = self.proposal_repository.get_for_review(review_id)
        review = self.review_repository.get_by_id(review_id)
        if review is None:
            return
        review.pending_proposals_count = sum(
            1 for item in proposals if item.status == PROPOSAL_STATUS_PENDING
        )
        review.rejected_count = sum(
            1 for item in proposals if item.status == PROPOSAL_STATUS_REJECTED
        )
        review.accepted_count = sum(
            1 for item in proposals if item.status == PROPOSAL_STATUS_INCORPORATED
        )
        review.unassigned_count = sum(
            1 for item in proposals if item.status == PROPOSAL_STATUS_UNASSIGNED
        )
        self.review_repository.update(review)

    def _active_events(self, template_id: int) -> list[HazardLibraryTemplateEvent]:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
            hazard_library_template_event_service,
        )

        return [
            event
            for event in hazard_library_template_event_service.get_for_template(
                template_id,
                include_inactive=False,
            )
        ]

    def _active_assessments(self, template_event_id: int) -> list[HazardLibraryTemplateAssessment]:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
            hazard_library_template_assessment_service,
        )

        return [
            row.assessment
            for row in hazard_library_template_assessment_service.get_for_event(
                template_event_id,
                include_inactive=False,
            )
        ]

    def _active_existing_measures(
        self,
        template_assessment_id: int,
    ) -> list[HazardLibraryTemplateExistingMeasure]:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
            hazard_library_template_existing_measure_service,
        )

        return hazard_library_template_existing_measure_service.get_for_assessment(
            template_assessment_id,
            include_inactive=False,
        )

    def _active_required_measures(
        self,
        template_assessment_id: int,
    ) -> list[HazardLibraryTemplateRequiredMeasure]:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
            hazard_library_template_required_measure_service,
        )

        return hazard_library_template_required_measure_service.get_for_assessment(
            template_assessment_id,
            include_inactive=False,
        )

    @staticmethod
    def _next_legal_link_sort_order(session, template_id: int) -> int:
        from sqlalchemy import func, select

        value = session.scalar(
            select(func.max(HazardLibraryTemplateLegalLink.sort_order)).where(
                HazardLibraryTemplateLegalLink.template_id == template_id,
            ),
        )
        return (value or 0) + 1

    @staticmethod
    def _next_event_sort_order(session, template_id: int) -> int:
        from sqlalchemy import func, select

        value = session.scalar(
            select(func.max(HazardLibraryTemplateEvent.sort_order)).where(
                HazardLibraryTemplateEvent.template_id == template_id,
            ),
        )
        return (value or 0) + 1

    @staticmethod
    def _next_assessment_sort_order(session, template_event_id: int) -> int:
        from sqlalchemy import func, select

        value = session.scalar(
            select(func.max(HazardLibraryTemplateAssessment.sort_order)).where(
                HazardLibraryTemplateAssessment.template_event_id == template_event_id,
            ),
        )
        return (value or 0) + 1

    @staticmethod
    def _next_existing_measure_sort_order(session, template_assessment_id: int) -> int:
        from sqlalchemy import func, select

        value = session.scalar(
            select(func.max(HazardLibraryTemplateExistingMeasure.sort_order)).where(
                HazardLibraryTemplateExistingMeasure.template_assessment_id
                == template_assessment_id,
            ),
        )
        return (value or 0) + 1

    @staticmethod
    def _next_required_measure_sort_order(session, template_assessment_id: int) -> int:
        from sqlalchemy import func, select

        value = session.scalar(
            select(func.max(HazardLibraryTemplateRequiredMeasure.sort_order)).where(
                HazardLibraryTemplateRequiredMeasure.template_assessment_id
                == template_assessment_id,
            ),
        )
        return (value or 0) + 1


hazard_catalog_proposal_incorporate_service = HazardCatalogProposalIncorporateService()
