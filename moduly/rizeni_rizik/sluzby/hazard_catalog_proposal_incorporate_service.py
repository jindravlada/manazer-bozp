"""Zapracování návrhů AI do MASTER obsahu katalogu zdrojů rizik (R18g)."""

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
from moduly.rizeni_rizik.constants import DEFAULT_RISK_SEVERITY, RISK_SEVERITIES
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
    HazardLibraryTemplateAssessment,
)
from moduly.rizeni_rizik.modely.hazard_library_template_event import HazardLibraryTemplateEvent
from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
    HazardLibraryTemplateExistingMeasure,
    HazardLibraryTemplateRequiredMeasure,
)
from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
    HazardLibraryTemplateRevision,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_DUPLICATE_ACTION_MERGE,
    CATALOG_DUPLICATE_ACTION_SKIP,
    CATALOG_PROPOSAL_KIND_ASSESSMENT,
    CATALOG_PROPOSAL_KIND_EVENT,
    CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
    CATALOG_PROPOSAL_KIND_EXPOSED_GROUP,
    CATALOG_PROPOSAL_KIND_LEGAL,
    CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
    CATALOG_PROPOSAL_KIND_UNKNOWN,
    CatalogProposalDuplicate,
    CatalogProposalPayload,
    classify_catalog_proposal,
    parse_proposal_payload,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    normalize_template_event_name,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    normalize_template_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardCatalogProposalIncorporateError(ValueError):
    pass


@dataclass
class CatalogIncorporateResult:
    incorporated_count: int
    skipped_count: int
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
        kind = classify_catalog_proposal(proposal)
        payload = parse_proposal_payload(proposal)

        if kind == CATALOG_PROPOSAL_KIND_EVENT:
            normalized = normalize_template_event_name(proposal.name)
            for event in self._active_events(template_id):
                if normalize_template_event_name(event.name) == normalized:
                    return CatalogProposalDuplicate(
                        kind=kind,
                        existing_label=event.name,
                        existing_id=event.id,
                    )
            return None

        if kind == CATALOG_PROPOSAL_KIND_ASSESSMENT:
            parent = self._resolve_parent(proposal, export_id_map)
            if parent is None or parent.get("kind") != "event":
                return None
            if proposal.exposed_group_id is None:
                return None
            for assessment in self._active_assessments(int(parent["id"])):
                if assessment.exposed_group_id == proposal.exposed_group_id:
                    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

                    group_name = exposed_group_service.display_name(assessment.exposed_group_id)
                    return CatalogProposalDuplicate(
                        kind=kind,
                        existing_label=group_name or "—",
                        existing_id=assessment.id,
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
            normalized = normalize_template_measure_description(description)
            measures = (
                self._active_existing_measures(int(parent["id"]))
                if kind == CATALOG_PROPOSAL_KIND_EXISTING_MEASURE
                else self._active_required_measures(int(parent["id"]))
            )
            for measure in measures:
                if normalize_template_measure_description(measure.description) == normalized:
                    return CatalogProposalDuplicate(
                        kind=kind,
                        existing_label=measure.description,
                        existing_id=measure.id,
                    )
            return None

        if kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

            normalized = normalize_template_event_name(proposal.name)
            for group in exposed_group_service.get_all(include_inactive=False):
                if normalize_template_event_name(group.name) == normalized:
                    return CatalogProposalDuplicate(
                        kind=kind,
                        existing_label=group.name,
                        existing_id=group.id,
                    )
            return None

        return None

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
    ) -> CatalogIncorporateResult:
        if not proposal_ids:
            raise HazardCatalogProposalIncorporateError("Vyberte alespoň jeden návrh ke zapracování.")

        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardCatalogProposalIncorporateError("Zdroj rizika neexistuje.")
        if not template.active:
            raise HazardCatalogProposalIncorporateError(
                "Návrhy lze zapracovat pouze do aktivního zdroje rizika."
            )

        review = self.review_repository.get_by_id(review_id)
        if review is None:
            raise HazardCatalogProposalIncorporateError("Konzultace neexistuje.")
        if review.source_id != template_id:
            raise HazardCatalogProposalIncorporateError("Konzultace nepatří k tomuto zdroji rizika.")

        export_id_map = self.get_export_id_map(review_id)
        proposals = [
            proposal
            for proposal in self.proposal_repository.get_by_ids(proposal_ids)
            if proposal.status == PROPOSAL_STATUS_PENDING
        ]
        if not proposals:
            raise HazardCatalogProposalIncorporateError(
                "Vybrané návrhy nejsou ve stavu čekajícím na odborné posouzení."
            )

        incorporated = 0
        skipped = 0
        merged = 0
        applied_any = False
        new_revision_number: int | None = None

        session = get_session()
        try:
            db_template = session.get(HazardLibraryTemplate, template_id)
            if db_template is None:
                raise HazardCatalogProposalIncorporateError("Zdroj rizika neexistuje.")

            for proposal in proposals:
                action = resolutions.get(proposal.id, "")
                if action == CATALOG_DUPLICATE_ACTION_SKIP:
                    skipped += 1
                    continue

                db_proposal = session.get(AiUnassignedProposal, proposal.id)
                if db_proposal is None or db_proposal.status != PROPOSAL_STATUS_PENDING:
                    continue

                kind = classify_catalog_proposal(db_proposal)
                if kind == CATALOG_PROPOSAL_KIND_LEGAL:
                    raise HazardCatalogProposalIncorporateError(
                        f"Právní vazbu „{db_proposal.name}“ nelze zapracovat do MASTER obsahu."
                    )
                if kind == CATALOG_PROPOSAL_KIND_UNKNOWN:
                    raise HazardCatalogProposalIncorporateError(
                        f"Návrh „{db_proposal.name}“ nelze zařadit do známé oblasti."
                    )

                if action == CATALOG_DUPLICATE_ACTION_MERGE:
                    db_proposal.status = PROPOSAL_STATUS_INCORPORATED
                    merged += 1
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
            skipped_count=skipped,
            merged_count=merged,
            new_revision_number=new_revision_number,
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
                    f"Návrh události „{proposal.name}“ nemá platný rodič SOURCE."
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
                    f"Návrh posouzení „{proposal.name}“ nemá platný rodič EVENT."
                )
            if proposal.exposed_group_id is None:
                raise HazardCatalogProposalIncorporateError(
                    f"Návrh posouzení „{proposal.name}“ nemá vybranou ohroženou skupinu."
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
                    f"Návrh opatření „{proposal.name}“ nemá platný rodič ASSESSMENT."
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
                    f"Návrh opatření „{proposal.name}“ nemá platný rodič ASSESSMENT."
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

        if kind == CATALOG_PROPOSAL_KIND_EXPOSED_GROUP:
            raise HazardCatalogProposalIncorporateError(
                "Návrh ohrožené skupiny zatím nelze přímo zapracovat do MASTER obsahu."
            )

        raise HazardCatalogProposalIncorporateError(
            f"Návrh „{proposal.name}“ nelze zapracovat."
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
