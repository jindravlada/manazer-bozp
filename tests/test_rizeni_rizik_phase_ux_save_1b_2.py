"""UX-SAVE-1b.2 – obnova posouzení po zapracování AI balíku."""

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

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
        AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageEvent,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.database.session import get_session
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_MANUAL
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
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        hazard_catalog_package_incorporate_service,
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
    from moduly.rizeni_rizik.ui.hazard_library_template_assessments_dialog import (
        HazardLibraryTemplateAssessmentsDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryUxSave1b2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci daného pracoviště")
        self.contractors = ensure_exposed_group("Dodavatelé")
        self.template = hazard_library_template_service.create_template(
            name=f"UX-SAVE-1b.2 {id(self)}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.export_id_map = hazard_catalog_package_incorporate_service.get_export_id_map(
            self.review.id,
        )

    def _patch_info(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        )

    def _store_package(self, package: AiProposalPackage) -> AiProposalPackageRecord:
        updated = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        return ai_peer_review_service.get_packages_for_review(updated.id)[0]

    def _open_assessments_for_first_event(self, dialog: HazardLibraryTemplateDialog):
        cw = dialog.content_widget
        cw.refresh()
        self.assertGreater(cw.events_table.rowCount(), 0)
        cw.events_table.selectRow(0)
        event = cw._selected_event()
        assert event is not None
        assessments = HazardLibraryTemplateAssessmentsDialog(
            cw,
            template_id=self.template.id,
            template_event_id=event.id,
            event_name=event.name,
            content_store=cw._store(),
        )
        return cw, event, assessments

    def test_new_assessment_visible_immediately(self) -> None:
        record = self._store_package(
            AiProposalPackage(
                package_id="new-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                reasoning="r",
                event=AiProposalPackageEvent(name="AI událost", description="", note=""),
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="závěr",
                        existing_measures=(
                            AiProposalPackageMeasure(description="Existující"),
                        ),
                        required_measures=(),
                    ),
                ),
                legal_links=(),
            ),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._on_catalog_proposals_incorporated(None)

        cw, event, assessments = self._open_assessments_for_first_event(dialog)
        summary = cw._store().count_active_assessments_by_events().get(event.id, 0)
        self.assertEqual(summary, 1)
        self.assertEqual(assessments._panel.table.rowCount(), 1)
        self.assertEqual(summary, assessments._panel.table.rowCount())

    def test_merged_assessment_detail_refreshes(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád předmětu",
        )
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Původní závěr",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=existing.id,
            description="Původní opatření",
        )
        # Nový export kvůli event id v mapě.
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            self.template.id,
            export_dir / "export2.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        export_id = next(
            key
            for key, value in hazard_catalog_package_incorporate_service.get_export_id_map(
                self.review.id,
            ).items()
            if isinstance(value, dict)
            and value.get("kind") == "event"
            and int(value.get("id")) == event.id
        )
        record = self._store_package(
            AiProposalPackage(
                package_id="merge-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
                target_event_export_id=export_id,
                event=None,
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_CRITICAL,
                        conclusion="Nový závěr AI",
                        existing_measures=(
                            AiProposalPackageMeasure(description="Nové opatření AI"),
                        ),
                        required_measures=(
                            AiProposalPackageMeasure(description="Potřebné AI"),
                        ),
                    ),
                ),
                legal_links=(),
                reasoning="merge",
            ),
        )

        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._on_catalog_proposals_incorporated(None)

        cw, selected_event, assessments = self._open_assessments_for_first_event(dialog)
        self.assertEqual(selected_event.id, event.id)
        self.assertEqual(assessments._panel.table.rowCount(), 1)
        store = cw._store()
        assert store is not None
        rows = store.get_assessments_for_event(event.id)
        self.assertEqual(len(rows), 1)
        assessment = store.get_assessment(rows[0].assessment.id)
        assert assessment is not None
        self.assertEqual(assessment.severity, RISK_SEVERITY_CRITICAL)
        self.assertIn("Nový závěr AI", assessment.conclusion)
        descriptions = {m.description for m in assessment.existing_measures if m.active}
        self.assertIn("Původní opatření", descriptions)
        self.assertIn("Nové opatření AI", descriptions)
        required = {m.description for m in assessment.required_measures if m.active}
        self.assertIn("Potřebné AI", required)

    def test_summary_matches_list_never_desynced(self) -> None:
        record = self._store_package(
            AiProposalPackage(
                package_id="sync-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                reasoning="r",
                event=AiProposalPackageEvent(name="Sync event", description="", note=""),
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="c",
                        existing_measures=(),
                        required_measures=(),
                    ),
                    AiProposalPackageAssessment(
                        exposed_group="Dodavatelé",
                        exposed_group_ids=(self.contractors.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="c2",
                        existing_measures=(),
                        required_measures=(),
                    ),
                ),
                legal_links=(),
            ),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._on_catalog_proposals_incorporated(None)

        cw, event, assessments = self._open_assessments_for_first_event(dialog)
        summary = cw._store().count_active_assessments_by_events().get(event.id, 0)
        self.assertEqual(summary, 2)
        self.assertEqual(assessments._panel.table.rowCount(), 2)
        self.assertNotEqual(assessments._panel.table.rowCount(), 0)

    def test_selected_event_preserved_after_refresh(self) -> None:
        event_a = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost A",
        )
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost B",
        )
        record = self._store_package(
            AiProposalPackage(
                package_id="sel-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                reasoning="r",
                event=AiProposalPackageEvent(name="Nová AI", description="", note=""),
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="c",
                        existing_measures=(),
                        required_measures=(),
                    ),
                ),
                legal_links=(),
            ),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        cw = dialog.content_widget
        cw.refresh()
        cw.select_event_by_id(event_a.id)
        self.assertEqual(cw._selected_event_id, event_a.id)

        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._on_catalog_proposals_incorporated(None)
        self.assertEqual(cw._selected_event_id, event_a.id)

    def test_cancel_discards_assessments(self) -> None:
        record = self._store_package(
            AiProposalPackage(
                package_id="cancel-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                reasoning="r",
                event=AiProposalPackageEvent(name="Dočasná", description="", note=""),
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="c",
                        existing_measures=(),
                        required_measures=(),
                    ),
                ),
                legal_links=(),
            ),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )

    def test_save_reload_shows_same_assessments(self) -> None:
        record = self._store_package(
            AiProposalPackage(
                package_id="save-1",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                reasoning="r",
                event=AiProposalPackageEvent(name="Uložená", description="", note=""),
                assessments=(
                    AiProposalPackageAssessment(
                        exposed_group="Zaměstnanci daného pracoviště",
                        exposed_group_ids=(self.group.id,),
                        severity=RISK_SEVERITY_MODERATE,
                        conclusion="c",
                        existing_measures=(
                            AiProposalPackageMeasure(description="Opatření"),
                        ),
                        required_measures=(),
                    ),
                ),
                legal_links=(),
            ),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        dialog2 = HazardLibraryTemplateDialog(template=reloaded)
        cw, event, assessments = self._open_assessments_for_first_event(dialog2)
        self.assertEqual(event.name, "Uložená")
        self.assertEqual(assessments._panel.table.rowCount(), 1)
        self.assertEqual(
            cw._store().count_active_assessments_by_events().get(event.id),
            1,
        )


if __name__ == "__main__":
    unittest.main()
