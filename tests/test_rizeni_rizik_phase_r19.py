"""Fáze R19 – právní vazby katalogu a dokončení AI workflow."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import (
        PROPOSAL_STATUS_INCORPORATED,
        PROPOSAL_STATUS_PENDING,
        AiUnassignedProposal,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions, AiProposal
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_INCORPORATE_ERROR_UNKNOWN_AREA,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
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
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
        LegalRequirementMatchKind,
        hazard_catalog_legal_requirement_resolver,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
        HazardCatalogProposalIncorporateError,
        hazard_catalog_proposal_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
        CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
        CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE,
        CATALOG_DUPLICATE_ACTION_MERGE,
        format_incorporate_summary,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogLegalLinksR19TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj R19",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.requirement = legal_requirement_service.create_requirement(
            title="BOZP dokumentace",
            process_code="P-901",
        )
        self.other_requirement = legal_requirement_service.create_requirement(
            title="BOZP dokumentace dodavatelů",
            process_code="P-902",
        )
        self.export_dir = Path(tempfile.mkdtemp())
        self.provider = hazard_catalog_source_peer_review_provider
        self.review = self._export().review

    def _export(self):
        target = self.export_dir / "export.zip"
        return ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )

    def _store_pending(self, proposals: list[AiProposal]) -> list[AiUnassignedProposal]:
        ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=proposals,
            rejected=[],
            loaded_proposals_count=len(proposals),
        )
        return [
            item
            for item in ai_peer_review_service.get_unassigned_for_review(self.review.id)
            if item.status == PROPOSAL_STATUS_PENDING
        ]

    def test_legal_link_crud(self) -> None:
        link = hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_requirement_id=self.requirement.id,
            note="Povinnost mít BOZP dokumentaci",
        )
        self.assertTrue(link.active)

        hazard_library_template_legal_link_service.deactivate_link(link.id)
        reloaded = hazard_library_template_legal_link_service.get_by_id(link.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        hazard_library_template_legal_link_service.activate_link(link.id)
        reloaded = hazard_library_template_legal_link_service.get_by_id(link.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_legal_requirement_resolver_exact_by_code(self) -> None:
        match = hazard_catalog_legal_requirement_resolver.resolve("P-901")
        self.assertEqual(match.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(match.requirement_id, self.requirement.id)

    def test_legal_proposal_auto_uses_existing_requirement(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Právní vazba",
                    name="P-901",
                    parent_export_id="SOURCE-001",
                    reasoning="Právní požadavek z AI",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(plan.conflicts, [])
        self.assertEqual(plan.pending_proposal_ids, [])
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions=plan.resolutions,
            pending_proposal_ids=plan.pending_proposal_ids,
        )
        self.assertEqual(result.newly_incorporated_count, 1)
        links = hazard_library_template_legal_link_service.get_for_template(self.template.id)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].legal_requirement_id, self.requirement.id)

    def test_legal_proposal_auto_merges_existing_link(self) -> None:
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_requirement_id=self.requirement.id,
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Právní vazba",
                    name="BOZP dokumentace",
                    parent_export_id="SOURCE-001",
                    reasoning="Duplicitní vazba",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(plan.resolutions[stored[0].id], CATALOG_DUPLICATE_ACTION_MERGE)
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions=plan.resolutions,
        )
        self.assertEqual(result.used_existing_count, 1)
        links = hazard_library_template_legal_link_service.get_for_template(self.template.id)
        self.assertEqual(len(links), 1)

    def test_legal_proposal_ambiguous_requires_choice(self) -> None:
        legal_requirement_service.create_requirement(
            title="Právní povinnost BOZP",
            process_code="P-903",
        )
        legal_requirement_service.create_requirement(
            title="Právní povinnost BOZP",
            process_code="P-904",
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Právní vazba",
                    name="Právní povinnost BOZP",
                    parent_export_id="SOURCE-001",
                    reasoning="Nejednoznačná shoda",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(plan.conflicts[0].conflict_type, CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE)
        self.assertGreaterEqual(len(plan.conflicts[0].requirement_candidates), 2)

    def test_legal_proposal_not_found_stays_pending(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Právní vazba",
                    name="Neexistující právní požadavek XYZ",
                    parent_export_id="SOURCE-001",
                    reasoning="Bez shody v RPP",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertIn(stored[0].id, plan.pending_proposal_ids)
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={},
            pending_proposal_ids=plan.pending_proposal_ids,
        )
        self.assertEqual(result.requires_manual_decision_count, 1)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_PENDING)

    def test_measure_without_assessment_requires_choice(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        other_group = ensure_exposed_group("Dodavatelé")
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=other_group.id,
            consequence="Pád",
            severity=RISK_SEVERITY_MODERATE,
        )
        self.review = self._export().review
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Existující opatření",
                    name="Ochranné brýle",
                    parent_export_id="SOURCE-001",
                    reasoning="Opatření bez posouzení",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(plan.conflicts[0].conflict_type, CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE)
        self.assertEqual(len(plan.conflicts[0].assessment_candidates), 2)

    def test_measure_assigned_to_assessment_incorporates(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        self.review = self._export().review
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        assessment_export_id = next(
            export_id
            for export_id, payload in export_id_map.items()
            if payload.get("kind") == "assessment"
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Existující opatření",
                    name="Ochranné brýle",
                    parent_export_id="SOURCE-001",
                    reasoning="Opatření bez posouzení",
                ),
            ],
        )
        hazard_catalog_proposal_incorporate_service.assign_proposal_assessment(
            stored[0].id,
            assessment_export_id,
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        assessment_conflicts = [
            item
            for item in plan.conflicts
            if item.conflict_type == CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE
        ]
        self.assertEqual(assessment_conflicts, [])
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions=plan.resolutions,
        )
        self.assertEqual(result.newly_incorporated_count, 1)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)

    def test_user_friendly_unknown_area_error(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Neznámá oblast",
                    name="Něco",
                    parent_export_id="SOURCE-001",
                    reasoning="Neznámé",
                ),
            ],
        )
        with self.assertRaises(HazardCatalogProposalIncorporateError) as context:
            hazard_catalog_proposal_incorporate_service.incorporate_proposals(
                template_id=self.template.id,
                review_id=self.review.id,
                proposal_ids=[stored[0].id],
                resolutions={},
            )
        self.assertEqual(
            str(context.exception),
            CATALOG_INCORPORATE_ERROR_UNKNOWN_AREA.format(name="Něco"),
        )

    def test_incorporation_summary_with_manual_decision(self) -> None:
        summary = format_incorporate_summary(
            newly_incorporated=2,
            used_existing=1,
            requires_manual_decision=1,
            skipped=0,
            rejected=0,
            revision=3,
        )
        self.assertIn("Vyžaduje ruční rozhodnutí:\n1", summary)

    def test_mixed_incorporation_completes_without_crash(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost R19",
        )
        self.review = self._export().review
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Nová událost",
                    parent_export_id="SOURCE-001",
                    reasoning="Nová",
                ),
                AiProposal(
                    proposal_id="P-002",
                    area="Právní vazba",
                    name="Neexistující požadavek",
                    parent_export_id="SOURCE-001",
                    reasoning="Bez shody",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[item.id for item in stored],
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[item.id for item in stored],
            resolutions=plan.resolutions,
            pending_proposal_ids=plan.pending_proposal_ids,
        )
        self.assertEqual(result.newly_incorporated_count, 1)
        self.assertEqual(result.requires_manual_decision_count, 1)


if __name__ == "__main__":
    unittest.main()
