"""Fáze R18g – zapracování návrhů AI do Katalogu zdrojů rizik."""

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
        PROPOSAL_STATUS_LABELS,
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
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
        HAZARD_LIBRARY_REVISION_REASON_LABELS,
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
        CATALOG_DUPLICATE_ACTION_SKIP,
        CATALOG_DUPLICATE_MATCH_EXACT,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_revision_service import (
        hazard_library_template_revision_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardCatalogProposalIncorporateR18gTestCase(unittest.TestCase):
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
        self.template = hazard_library_template_service.create_template(
            name="Zdroj R18g",
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

    def test_pending_status_label(self) -> None:
        self.assertEqual(
            PROPOSAL_STATUS_LABELS[PROPOSAL_STATUS_PENDING],
            "Čeká na odborné posouzení",
        )

    def test_incorporate_single_event_proposal(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Pád břemene",
                    parent_export_id="SOURCE-001",
                    reasoning="Nová událost z AI",
                ),
            ],
        )
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={},
        )
        self.assertEqual(result.incorporated_count, 1)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Pád břemene")

        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)

    def test_bulk_incorporate_bumps_revision_once(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Událost A",
                    parent_export_id="SOURCE-001",
                    reasoning="A",
                ),
                AiProposal(
                    proposal_id="P-002",
                    area="Nežádoucí událost",
                    name="Událost B",
                    parent_export_id="SOURCE-001",
                    reasoning="B",
                ),
            ],
        )
        previous_version = self.template.version_number
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[item.id for item in stored],
            resolutions={},
        )
        self.assertEqual(result.incorporated_count, 2)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, previous_version + 1)

    def test_incorporate_creates_single_history_record(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Historie událost",
                    parent_export_id="SOURCE-001",
                    reasoning="Historie",
                ),
            ],
        )
        hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={},
        )
        rows = hazard_library_template_revision_service.get_rows(self.template.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].revision_number, 2)
        self.assertEqual(
            rows[0].reason_label,
            HAZARD_LIBRARY_REVISION_REASON_LABELS[HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS],
        )

    def test_rejected_proposal_not_written_to_master(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="Zamítnutá událost",
                    parent_export_id="SOURCE-001",
                    reasoning="Zamítnout",
                ),
            ],
        )
        rejected = hazard_catalog_proposal_incorporate_service.reject_proposals([stored[0].id])
        self.assertEqual(rejected, 1)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 0)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_REJECTED)
        still_stored = ai_peer_review_service.get_unassigned_for_review(self.review.id)
        self.assertEqual(len(still_stored), 1)

    def test_duplicate_event_detection(self) -> None:
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
        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(
            self.review.id,
        )
        duplicate = hazard_catalog_proposal_incorporate_service.detect_duplicate(
            template_id=self.template.id,
            proposal=stored[0],
            export_id_map=export_id_map,
        )
        self.assertIsNotNone(duplicate)
        assert duplicate is not None
        self.assertEqual(duplicate.existing_label, "Existující událost")
        self.assertEqual(duplicate.match_type, CATALOG_DUPLICATE_MATCH_EXACT)

    def test_duplicate_skip_does_not_create_event(self) -> None:
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
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={stored[0].id: CATALOG_DUPLICATE_ACTION_SKIP},
        )
        self.assertEqual(result.skipped_count, 1)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_PENDING)

    def test_duplicate_merge_marks_incorporated_without_new_event(self) -> None:
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
        result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={stored[0].id: CATALOG_DUPLICATE_ACTION_MERGE},
        )
        self.assertEqual(result.merged_count, 1)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        updated = ai_peer_review_service.get_proposal_by_id(stored[0].id)
        assert updated is not None
        self.assertEqual(updated.status, PROPOSAL_STATUS_INCORPORATED)

    def test_ui_refresh_after_incorporate(self) -> None:
        stored = self._store_pending(
            [
                AiProposal(
                    proposal_id="P-001",
                    area="Nežádoucí událost",
                    name="UI událost",
                    parent_export_id="SOURCE-001",
                    reasoning="UI",
                ),
            ],
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._on_catalog_proposals_incorporated(None)
        self.assertEqual(dialog.version_number.value(), 1)

        hazard_catalog_proposal_incorporate_service.incorporate_proposals(
            template_id=self.template.id,
            review_id=self.review.id,
            proposal_ids=[stored[0].id],
            resolutions={},
        )
        dialog._on_catalog_proposals_incorporated(2)
        self.assertEqual(dialog.version_number.value(), 2)

        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget.refresh()
        self.assertEqual(widget.proposals_table.rowCount(), 0)
        self.assertEqual(widget.table.item(0, 5).text(), "0")


if __name__ == "__main__":
    unittest.main()
