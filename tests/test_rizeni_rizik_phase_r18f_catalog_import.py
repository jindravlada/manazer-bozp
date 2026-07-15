"""HOTFIX R18f.1 – evidence importovaných návrhů v Katalogu zdrojů rizik."""

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
        PROPOSAL_STATUS_PENDING,
        PROPOSAL_STATUS_REJECTED,
        AiUnassignedProposal,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions, AiProposal
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
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
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _build_proposals(count: int, *, prefix: str = "Návrh") -> list[AiProposal]:
    return [
        AiProposal(
            proposal_id=f"P-{index:03d}",
            area="Nežádoucí událost",
            name=f"{prefix} {index}",
            parent_export_id="SOURCE-001",
            reasoning=f"Zdůvodnění {index}",
        )
        for index in range(1, count + 1)
    ]


class HazardCatalogImportEvidenceR18f1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
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
        self.template = hazard_library_template_service.create_template(
            name="Testovací zdroj",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        self.export_dir = Path(tempfile.mkdtemp())
        self.provider = hazard_catalog_source_peer_review_provider

    def _export(self):
        target = self.export_dir / "export.zip"
        return ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )

    def test_accepted_proposals_stored_as_pending(self) -> None:
        export_result = self._export()
        accepted = _build_proposals(21)
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=accepted,
            rejected=[],
            loaded_proposals_count=23,
        )
        stored = ai_peer_review_service.get_unassigned_for_review(updated.id)
        self.assertEqual(len(stored), 21)
        self.assertTrue(all(item.status == PROPOSAL_STATUS_PENDING for item in stored))
        self.assertEqual(updated.pending_proposals_count, 21)
        self.assertEqual(updated.accepted_count, 0)

    def test_rejected_proposals_stored_as_rejected(self) -> None:
        export_result = self._export()
        rejected = _build_proposals(2, prefix="Zamítnutý")
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=[],
            rejected=rejected,
            loaded_proposals_count=2,
        )
        stored = ai_peer_review_service.get_unassigned_for_review(updated.id)
        self.assertEqual(len(stored), 2)
        self.assertTrue(all(item.status == PROPOSAL_STATUS_REJECTED for item in stored))
        self.assertEqual(updated.rejected_count, 2)
        self.assertEqual(updated.pending_proposals_count, 0)

    def test_mixed_import_summary_counts(self) -> None:
        export_result = self._export()
        accepted = _build_proposals(21)
        rejected = _build_proposals(2, prefix="Zamítnutý")
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=accepted,
            rejected=rejected,
            loaded_proposals_count=23,
        )
        self.assertEqual(updated.loaded_proposals_count, 23)
        self.assertEqual(updated.pending_proposals_count, 21)
        self.assertEqual(updated.rejected_count, 2)
        self.assertEqual(updated.accepted_count, 0)
        self.assertEqual(updated.unassigned_count, 0)

    def test_proposals_persist_after_reload(self) -> None:
        export_result = self._export()
        accepted = _build_proposals(3)
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=accepted,
            rejected=[],
            loaded_proposals_count=3,
        )
        reloaded = ai_peer_review_service.get_unassigned_for_review(updated.id)
        self.assertEqual(len(reloaded), 3)
        self.assertEqual(reloaded[0].ai_peer_review_id, updated.id)
        self.assertEqual(reloaded[0].proposal_id, "P-001")
        self.assertEqual(reloaded[0].parent_export_id, "SOURCE-001")

    def test_second_import_creates_new_consultation_record(self) -> None:
        export_result = self._export()
        first = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text="první odpověď",
            ai_model="Claude",
            accepted=_build_proposals(1),
            rejected=[],
            loaded_proposals_count=1,
        )
        clone = ai_peer_review_service.clone_consultation_for_new_import(first.id)
        second = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=clone.id,
            response_text="druhá odpověď",
            ai_model="GPT",
            accepted=_build_proposals(2, prefix="Druhý"),
            rejected=[],
            loaded_proposals_count=2,
        )
        reviews = ai_peer_review_service.get_for_source(
            self.provider.source_type,
            self.template.id,
        )
        self.assertEqual(len(reviews), 2)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(len(ai_peer_review_service.get_unassigned_for_review(first.id)), 1)
        self.assertEqual(len(ai_peer_review_service.get_unassigned_for_review(second.id)), 2)

    def test_replace_import_deletes_previous_proposals(self) -> None:
        export_result = self._export()
        review_id = export_result.review.id
        ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=review_id,
            response_text="původní odpověď",
            ai_model="Claude",
            accepted=_build_proposals(4),
            rejected=[],
            loaded_proposals_count=4,
        )
        self.assertEqual(len(ai_peer_review_service.get_unassigned_for_review(review_id)), 4)
        ai_peer_review_service.delete_proposals_for_review(review_id)
        ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=review_id,
            response_text="nová odpověď",
            ai_model="Claude",
            accepted=_build_proposals(1, prefix="Nový"),
            rejected=_build_proposals(1, prefix="Zamítnutý"),
            loaded_proposals_count=2,
        )
        stored = ai_peer_review_service.get_unassigned_for_review(review_id)
        self.assertEqual(len(stored), 2)
        names = {item.name for item in stored}
        self.assertIn("Nový 1", names)
        self.assertIn("Zamítnutý 1", names)

    def test_widget_refreshes_history_and_proposals_after_import(self) -> None:
        from core.ai_oponentni.constants import AI_PEER_REVIEW_COL_PENDING

        export_result = self._export()
        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        self.assertEqual(widget.table.rowCount(), 1)

        ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text='{"schema_version":"1.1","proposals":[]}',
            ai_model="Claude",
            accepted=_build_proposals(2),
            rejected=_build_proposals(1, prefix="Zamítnutý"),
            loaded_proposals_count=3,
        )
        widget.refresh()
        self.assertEqual(widget.table.rowCount(), 1)
        self.assertEqual(
            widget.table.item(0, AI_PEER_REVIEW_COL_PENDING).text(),
            "2",
        )
        self.assertEqual(widget.proposals_table.rowCount(), 2)

    def test_catalog_dialog_uses_evidence_only_import(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        self.assertTrue(dialog.ai_peer_review_widget._evidence_only_import)


if __name__ == "__main__":
    unittest.main()
