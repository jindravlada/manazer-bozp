"""HOTFIX R18g.2 – inteligentní zpracování duplicit při zapracování AI návrhů."""

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
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_PROPOSAL_DUPLICATE_SIMILAR_INTRO,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
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
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
        hazard_catalog_proposal_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
        CATALOG_DUPLICATE_ACTION_MERGE,
        CATALOG_DUPLICATE_MATCH_EXACT,
        CATALOG_DUPLICATE_MATCH_SIMILAR,
        format_incorporate_summary,
        requires_dialog_for_duplicate,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_proposal_duplicate_dialog import (
        HazardCatalogProposalDuplicateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogProposalDuplicateR18g2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.suppliers = ensure_exposed_group("Dodavatelé")
        self.template = hazard_library_template_service.create_template(
            name="Zdroj R18g.2",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
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

    def test_auto_resolve_exposed_group_for_assessment(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz jeřábu",
        )
        self.review = self._export().review
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        event_export_id = next(
            export_id
            for export_id, payload in export_id_map.items()
            if payload.get("kind") == "event"
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Posouzení rizik – ohrožená skupina",
                    name="Zaměstnanci",
                    parent_export_id=event_export_id,
                    reasoning="Posouzení pro zaměstnance",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(plan.conflicts, [])
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.exposed_group_id, self.group.id)

    def test_exact_exposed_group_match_auto_merges_without_conflict(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Ohrožené skupiny",
                    name="Dodavatelé",
                    parent_export_id="SOURCE-001",
                    reasoning="Existující skupina",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(plan.conflicts, [])
        self.assertEqual(plan.resolutions[stored[0].id], CATALOG_DUPLICATE_ACTION_MERGE)

        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions=plan.resolutions,
        )
        self.assertEqual(result.used_existing_count, 1)
        self.assertEqual(result.newly_incorporated_count, 0)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)

    def test_exact_event_match_has_no_conflict(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Existující událost",
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Existující událost",
                    parent_export_id="SOURCE-001",
                    reasoning="Duplicita",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(plan.conflicts, [])
        self.assertEqual(plan.resolutions[stored[0].id], CATALOG_DUPLICATE_ACTION_MERGE)

    def test_similar_event_match_requires_dialog(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Údržba a servis jeřábu",
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Údržba jeřábu",
                    parent_export_id="SOURCE-001",
                    reasoning="Podobná událost",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(len(plan.conflicts), 1)
        conflict = plan.conflicts[0]
        self.assertEqual(conflict.proposal_id, stored[0].id)
        self.assertEqual(conflict.duplicate.match_type, CATALOG_DUPLICATE_MATCH_SIMILAR)
        self.assertTrue(requires_dialog_for_duplicate(conflict.duplicate))
        self.assertNotIn(stored[0].id, plan.resolutions)

    def test_similar_existing_measure_requires_dialog(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Provoz",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Používat ochranné brýle a rukavice",
        )
        self.review = self._export().review
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        assessment_export_id = next(
            export_id
            for export_id, payload in export_id_map.items()
            if payload.get("kind") == "assessment" and payload.get("id") == assessment.id
        )
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Existující opatření",
                    name="Používat ochranné brýle",
                    parent_export_id=assessment_export_id,
                    reasoning="Podobné opatření",
                ),
            ],
        )
        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
        )
        self.assertEqual(len(plan.conflicts), 1)
        self.assertEqual(plan.conflicts[0].duplicate.match_type, CATALOG_DUPLICATE_MATCH_SIMILAR)

    def test_similar_match_duplicate_dialog_uses_similar_intro(self) -> None:
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
            CatalogProposalDuplicate,
        )

        duplicate = CatalogProposalDuplicate(
            kind="event",
            match_type=CATALOG_DUPLICATE_MATCH_SIMILAR,
            existing_label="Údržba a servis jeřábu",
        )
        dialog = HazardCatalogProposalDuplicateDialog(
            None,
            proposal_name="Údržba jeřábu",
            duplicate=duplicate,
        )
        from PySide6.QtWidgets import QLabel

        labels = dialog.findChildren(QLabel)
        self.assertTrue(labels)
        expected = CATALOG_AI_PROPOSAL_DUPLICATE_SIMILAR_INTRO.format(
            proposal_name="Údržba jeřábu",
            existing_label="Údržba a servis jeřábu",
        )
        self.assertEqual(labels[0].text(), expected)

    def test_format_incorporate_summary(self) -> None:
        summary = format_incorporate_summary(
            newly_incorporated=18,
            used_existing=3,
            skipped=1,
            rejected=2,
            revision=5,
        )
        self.assertIn("Zapracování dokončeno.", summary)
        self.assertIn("Nově zapracováno:\n18", summary)
        self.assertIn("Použito existujících položek:\n3", summary)
        self.assertIn("Přeskočeno:\n1", summary)
        self.assertIn("Zamítnuto:\n2", summary)
        self.assertIn("Nová revize:\n5", summary)

    def test_incorporate_summary_counts_after_auto_merge(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Existující událost",
        )
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
                    area="Nežádoucí událost",
                    name="Existující událost",
                    parent_export_id="SOURCE-001",
                    reasoning="Duplicita",
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
        )
        self.assertEqual(result.newly_incorporated_count, 1)
        self.assertEqual(result.used_existing_count, 1)
        self.assertEqual(result.incorporated_count, 2)


if __name__ == "__main__":
    unittest.main()
