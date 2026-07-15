"""HOTFIX R19.2 – dokončení ručního přiřazení opatření k posouzení."""

from __future__ import annotations

import importlib
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
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
        hazard_catalog_proposal_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
        CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
        CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service


class HazardCatalogMeasureAssignmentR19_2TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

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
            session.commit()

        self.template = hazard_library_template_service.create_template(
            name="Zdroj R19.2",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.group = exposed_group_service.get_all(include_inactive=False)[0]
        self.provider = hazard_catalog_source_peer_review_provider
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export.zip",
            options=AiPeerReviewExportOptions(),
        ).review

    def _store_pending(self, proposals: list[AiProposal]):
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
        return ai_peer_review_service.get_unassigned_for_review(self.review.id)

    def test_single_assessment_is_auto_assigned_without_conflict(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export2.zip",
            options=AiPeerReviewExportOptions(),
        ).review
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
        assessment_conflicts = [
            item
            for item in plan.conflicts
            if item.conflict_type
            in {
                CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
                CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE,
            }
        ]
        self.assertEqual(assessment_conflicts, [])
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertTrue((updated.parent_export_id or "").startswith("ASSESSMENT-"))

    def test_measure_without_assessment_offers_create_conflict(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export3.zip",
            options=AiPeerReviewExportOptions(),
        ).review
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Potřebné opatření",
                    name="Instruktáž",
                    parent_export_id="SOURCE-001",
                    reasoning="Bez posouzení",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(plan.conflicts[0].conflict_type, CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE)
        self.assertGreaterEqual(len(plan.conflicts[0].template_event_choices), 1)

    def test_assessment_assignment_incorporates_measure(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export4.zip",
            options=AiPeerReviewExportOptions(),
        ).review
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
        hazard_catalog_proposal_incorporate_service.assign_proposal_assessment_by_id(
            stored[0].id,
            self.review.id,
            assessment.id,
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_single_proposal(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_id=stored[0].id,
            resolutions=plan.resolutions,
        )
        self.assertEqual(result.newly_incorporated_count, 1)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)

    def test_assessment_created_after_export_is_listed_as_candidate(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        self.review = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export5.zip",
            options=AiPeerReviewExportOptions(),
        ).review
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
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
        proposal = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert proposal is not None
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        candidates = hazard_catalog_proposal_incorporate_service._list_suitable_assessment_candidates(
            self.template.id,
            self.review.id,
            proposal,
            export_id_map,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].assessment_id, assessment.id)
        self.assertTrue(candidates[0].export_id.startswith("ASSESSMENT-"))


if __name__ == "__main__":
    unittest.main()
