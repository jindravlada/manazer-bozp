"""RISK-AI-MEASURE-RECOMMENDATION-EDIT-1: editor doporučení k opatřením."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-mrec-edit-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.ai_oponentni.constants import (
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_NEW_REQUIRED,
        AI_MEASURE_REC_NO_CHANGE,
        AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_PENDING,
        PACKAGE_STATUS_REJECTED,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageEvent,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.proposal_package_parser import (
        parse_ai_proposal_packages_response,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
    from core.database.session import get_session
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_CONTROL_QUESTION_EDIT_DIALOG_TITLE,
        CATALOG_AI_CONTROL_QUESTION_NEW_DIALOG_TITLE,
        CATALOG_AI_PACKAGE_EDIT_BUTTON,
        CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
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
        HazardCatalogPackageIncorporateError,
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        catalog_source_reference,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_ai_measure_recommendation_edit_dialog import (
        HazardCatalogAiMeasureRecommendationEditDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
        HazardCatalogAiPackageEditDialog,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskAiMeasureRecommendationEdit1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
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

        self.group = ensure_exposed_group("Obsluha MREC-EDIT")
        self.provider = hazard_catalog_source_peer_review_provider
        self.template = hazard_library_template_service.create_template(
            name="Zdroj MREC-EDIT",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Závěr",
        )
        self.assessment_id = int(assessment.id)
        self.existing = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.assessment_id,
            description="Používejte OOPP při manipulaci.",
        )
        self.required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.assessment_id,
            description="Kontrolujte uchycení břemene.",
        )
        self.export_dir = Path(tempfile.mkdtemp(prefix="risk-ai-mrec-export-"))
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.export_id_map = json.loads(self.review.export_id_map_json or "{}")
        self.reference = catalog_source_reference(self.template.id)
        self.initial_version = hazard_library_template_service.get_by_id(
            self.template.id,
        ).version_number

    def _export_id_for(self, kind: str, entity_id: int) -> str:
        for export_id, meta in self.export_id_map.items():
            if meta.get("kind") == kind and int(meta.get("id")) == int(entity_id):
                return export_id
        self.fail(f"Export ID pro {kind}/{entity_id} nenalezeno")

    def _store(self, package: AiProposalPackage) -> AiProposalPackageRecord:
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="test",
            accepted=[package],
            rejected=[],
        )
        stored = [
            record
            for record in ai_peer_review_service.get_packages_for_review(updated.id)
            if record.package_id == package.package_id
        ]
        self.assertEqual(len(stored), 1)
        return stored[0]

    def _recommendation(
        self,
        *,
        rec_id: str,
        rec_type: str,
        target_export_id: str,
        proposed_text: str,
        reasoning: str = "Zdůvodnění AI.",
    ) -> AiProposalPackage:
        return AiProposalPackage(
            package_id=rec_id,
            package_type=rec_type,
            target_event_export_id=None,
            event=None,
            assessments=(),
            legal_links=(),
            reasoning=reasoning,
            target_export_id=target_export_id,
            proposed_text=proposed_text,
        )

    def _event_package(self) -> AiProposalPackage:
        return AiProposalPackage(
            package_id="PKG-EVENT",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád z výšky"),
            assessments=(),
            legal_links=(),
            reasoning="Chybí událost.",
        )

    def _select_stored(self, record: AiProposalPackageRecord) -> AiPeerReviewWidget:
        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget._select_review_row(self.review.id)
        widget._load_proposals_table()
        widget._select_proposal_row(record.id)
        return widget

    def _catalog_snapshot(self) -> tuple[str, str, int, int]:
        existing = hazard_library_template_existing_measure_service.get_by_id(
            self.existing.id,
        )
        required = hazard_library_template_required_measure_service.get_by_id(
            self.required.id,
        )
        required_count = len(
            hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        )
        template = hazard_library_template_service.get_by_id(self.template.id)
        return (
            existing.description,
            required.description,
            required_count,
            template.version_number,
        )

    def test_01_proposal_package_opens_event_editor(self) -> None:
        record = self._store(self._event_package())
        widget = self._select_stored(record)
        captured: dict = {}

        def fake_exec(dialog):
            captured["dialog"] = dialog
            return False

        with patch("core.widgets.dialog_utils.exec_maximized", side_effect=fake_exec):
            widget._edit_selected_package()
        self.assertIsInstance(captured["dialog"], HazardCatalogAiPackageEditDialog)
        self.assertEqual(
            captured["dialog"].windowTitle(),
            CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE,
        )

    def test_02_measure_recommendation_opens_measure_editor(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-NEW",
                rec_type=AI_MEASURE_REC_NEW_REQUIRED,
                target_export_id=self._export_id_for("assessment", self.assessment_id),
                proposed_text="Nevstupujte pod zavěšené břemeno.",
            )
        )
        widget = self._select_stored(record)
        captured: dict = {}

        def fake_exec(dialog_self):
            captured["dialog"] = dialog_self
            return 0

        with (
            patch("core.widgets.dialog_utils.exec_maximized") as maximized,
            patch.object(
                HazardCatalogAiMeasureRecommendationEditDialog,
                "exec",
                fake_exec,
            ),
            patch(
                "core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.information",
            ) as info,
        ):
            widget._edit_selected_package()
        maximized.assert_not_called()
        for call in info.call_args_list:
            self.assertNotIn("nelze editovat jako balík", str(call))
        self.assertIsInstance(
            captured["dialog"],
            HazardCatalogAiMeasureRecommendationEditDialog,
        )
        self.assertEqual(
            captured["dialog"].windowTitle(),
            CATALOG_AI_CONTROL_QUESTION_NEW_DIALOG_TITLE,
        )
        self.assertEqual(widget.edit_proposal_btn.text(), CATALOG_AI_PACKAGE_EDIT_BUTTON)

    def test_03_new_required_measure_can_be_edited(self) -> None:
        package = self._recommendation(
            rec_id="MR-NEW",
            rec_type=AI_MEASURE_REC_NEW_REQUIRED,
            target_export_id=self._export_id_for("assessment", self.assessment_id),
            proposed_text="Původní návrh.",
        )
        dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=package,
            package_record_id=0,
            review_id=self.review.id,
        )
        self.assertIn("Pád břemene", dialog.target_field.toPlainText())
        dialog.proposed_text.setPlainText("Upravený zákaz vstupu pod břemeno.")
        dialog.reasoning.setPlainText("Doplněné zdůvodnění.")
        dialog.accept()
        updated = dialog.get_package()
        self.assertIsNotNone(updated)
        self.assertEqual(updated.proposed_text, "Upravený zákaz vstupu pod břemeno.")
        self.assertEqual(updated.reasoning, "Doplněné zdůvodnění.")
        self.assertEqual(updated.package_type, AI_MEASURE_REC_NEW_REQUIRED)
        self.assertEqual(updated.target_export_id, package.target_export_id)

    def test_04_edit_existing_required_measure_shows_current_text(self) -> None:
        target = self._export_id_for("required_measure", self.required.id)
        package = self._recommendation(
            rec_id="MR-EDIT",
            rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
            target_export_id=target,
            proposed_text="Původní návrh úpravy.",
        )
        dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=package,
            package_record_id=0,
            review_id=self.review.id,
        )
        self.assertIn("Kontrolujte uchycení břemene.", dialog.current_text.toPlainText())
        dialog.proposed_text.setPlainText("Před zdvihem ověřte uchycení břemene.")
        dialog.accept()
        updated = dialog.get_package()
        self.assertEqual(updated.proposed_text, "Před zdvihem ověřte uchycení břemene.")
        self.assertEqual(updated.target_export_id, target)

    def test_05_cancel_leaves_queue_and_catalog_unchanged(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-CANCEL",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id=self._export_id_for("required_measure", self.required.id),
                proposed_text="Původní návrh.",
            )
        )
        before = self._catalog_snapshot()
        dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=ai_peer_review_service.package_repository.package_from_record(record),
            package_record_id=record.id,
            review_id=self.review.id,
        )
        dialog.proposed_text.setPlainText("Toto se nesmí uložit.")
        dialog.reject()
        self.assertIsNone(dialog.get_package())
        reloaded = ai_peer_review_service.package_repository.package_from_record(
            ai_peer_review_service.package_repository.get_by_id(record.id),
        )
        self.assertEqual(reloaded.proposed_text, "Původní návrh.")
        self.assertEqual(self._catalog_snapshot(), before)

    def test_06_save_changes_only_queue_payload(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-SAVE",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id=self._export_id_for("required_measure", self.required.id),
                proposed_text="Původní návrh.",
            )
        )
        before = self._catalog_snapshot()
        package = ai_peer_review_service.package_repository.package_from_record(record)
        updated = package.with_editable_measure_fields(
            proposed_text="Uložené znění ve frontě.",
            reasoning="Nové zdůvodnění.",
        )
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            updated,
        )
        reloaded = ai_peer_review_service.package_repository.package_from_record(
            ai_peer_review_service.package_repository.get_by_id(record.id),
        )
        self.assertEqual(reloaded.proposed_text, "Uložené znění ve frontě.")
        self.assertEqual(reloaded.reasoning, "Nové zdůvodnění.")
        self.assertEqual(self._catalog_snapshot(), before)

    def test_07_incorporate_uses_edited_text(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-EDIT-INC",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id=self._export_id_for("required_measure", self.required.id),
                proposed_text="Původní návrh.",
            )
        )
        package = ai_peer_review_service.package_repository.package_from_record(record)
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            package.with_editable_measure_fields(
                proposed_text="Před zdvihem ověřte uchycení břemene.",
                reasoning=package.reasoning,
            ),
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        required = hazard_library_template_required_measure_service.get_by_id(
            self.required.id,
        )
        self.assertEqual(
            required.description,
            "Před zdvihem ověřte uchycení břemene.",
        )

    def test_08_direct_incorporate_without_edit(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-DIRECT",
                rec_type=AI_MEASURE_REC_NEW_REQUIRED,
                target_export_id=self._export_id_for("assessment", self.assessment_id),
                proposed_text="Nevstupujte pod zavěšené břemeno.",
            )
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        descriptions = [
            item.description
            for item in hazard_library_template_required_measure_service.get_for_assessment(
                self.assessment_id,
                include_inactive=False,
            )
        ]
        self.assertIn("Nevstupujte pod zavěšené břemeno.", descriptions)

    def test_09_reject_does_not_write_catalog(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-REJECT",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id=self._export_id_for("required_measure", self.required.id),
                proposed_text="Toto se nesmí zapsat.",
            )
        )
        before = self._catalog_snapshot()
        self.assertTrue(
            hazard_catalog_package_incorporate_service.reject_package(record.id),
        )
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_REJECTED)
        self.assertEqual(self._catalog_snapshot(), before)

    def test_10_type_and_target_export_id_cannot_change(self) -> None:
        original_target = self._export_id_for("required_measure", self.required.id)
        record = self._store(
            self._recommendation(
                rec_id="MR-LOCK",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id=original_target,
                proposed_text="Původní návrh.",
            )
        )
        tampered = AiProposalPackage(
            package_id="OTHER-ID",
            package_type=AI_MEASURE_REC_NEW_REQUIRED,
            target_event_export_id="EVENT-999",
            event=None,
            assessments=(),
            legal_links=(),
            reasoning="Cizí zdůvodnění.",
            target_export_id=self._export_id_for("assessment", self.assessment_id),
            proposed_text="Pokus o přesměrování.",
        )
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            tampered,
        )
        reloaded = ai_peer_review_service.package_repository.package_from_record(
            ai_peer_review_service.package_repository.get_by_id(record.id),
        )
        self.assertEqual(reloaded.package_id, "MR-LOCK")
        self.assertEqual(reloaded.package_type, AI_MEASURE_REC_EDIT_REQUIRED)
        self.assertEqual(reloaded.target_export_id, original_target)
        self.assertIsNone(reloaded.target_event_export_id)
        self.assertEqual(reloaded.proposed_text, "Pokus o přesměrování.")

    def test_11_invalid_target_does_not_partially_write(self) -> None:
        record = self._store(
            self._recommendation(
                rec_id="MR-BAD",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                target_export_id="REQUIRED-MEASURE-999",
                proposed_text="Neplatný cíl.",
            )
        )
        before = self._catalog_snapshot()
        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service.incorporate_package(
                template_id=self.template.id,
                package_record_id=record.id,
            )
        self.assertEqual(self._catalog_snapshot(), before)
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)

    def test_12_legacy_schema_2_0_response_still_works(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": self.reference,
            "proposal_packages": [],
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-LEGACY",
                    "typ": AI_MEASURE_REC_EDIT_REQUIRED,
                    "target_export_id": self._export_id_for(
                        "required_measure",
                        self.required.id,
                    ),
                    "proposed_text": "Před zdvihem ověřte uchycení.",
                    "reasoning": "Historická odpověď.",
                },
                {
                    "recommendation_id": "MR-NONE",
                    "typ": AI_MEASURE_REC_NO_CHANGE,
                    "reasoning": "Beze změn.",
                },
            ],
        }
        parsed = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=self.reference,
        )
        accepted, _duplicates = ai_peer_review_service.filter_new_packages_for_review(
            review_id=self.review.id,
            packages=parsed.packages,
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].package_id, "MR-LEGACY")
        record = self._store(accepted[0])
        dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=accepted[0],
            package_record_id=record.id,
            review_id=self.review.id,
        )
        self.assertEqual(
            dialog.windowTitle(),
            CATALOG_AI_CONTROL_QUESTION_EDIT_DIALOG_TITLE,
        )
        dialog.reject()

    def test_13_empty_catalog_starter_packages_still_work(self) -> None:
        empty = hazard_library_template_service.create_template(
            name="Prázdný starter",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        export_result = ai_peer_review_service.export_package(
            self.provider,
            empty.id,
            self.export_dir / "starter.zip",
            options=AiPeerReviewExportOptions(),
        )
        package = AiProposalPackage(
            package_id="PKG-STARTER",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="První událost"),
            assessments=(),
            legal_links=(),
            reasoning="První návrh.",
        )
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
            review_id=export_result.review.id,
        )
        self.assertEqual(dialog.windowTitle(), CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE)
        self.assertFalse(package.is_measure_recommendation)
        dialog.reject()


if __name__ == "__main__":
    unittest.main()
