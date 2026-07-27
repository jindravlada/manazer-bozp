"""Fáze R20d – ergonomie editoru návrhového balíku."""

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
        AiProposalPackageLegalLink,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
        RISK_SEVERITY_SERIOUS,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON,
        CATALOG_AI_PACKAGE_SUMMARY_TITLE,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
        HazardCatalogAiPackageEditDialog,
        assessment_section_title,
        format_package_summary,
        resolve_target_event_name,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class AiProposalPackageEditorR20dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group_a = ensure_exposed_group("Zaměstnanci daného pracoviště")
        self.group_b = ensure_exposed_group("Návštěvy a další osoby")
        self.template = hazard_library_template_service.create_template(
            name="Testovací zdroj R20d",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.existing_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Přejetí osoby lokomotivou",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.existing_event.id,
            exposed_group_id=self.group_a.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        self.provider = hazard_catalog_source_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        export_map = hazard_catalog_package_incorporate_service.get_export_id_map(
            self.review.id,
        )
        self.event_export_id = next(
            key
            for key, value in export_map.items()
            if isinstance(value, dict) and value.get("kind") == "event"
        )

    def _store_package(self, package: AiProposalPackage) -> AiProposalPackageRecord:
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        stored = ai_peer_review_service.get_packages_for_review(updated.id)
        self.assertGreaterEqual(len(stored), 1)
        return stored[-1]

    def _multi_assessment_package(self) -> AiProposalPackage:
        return AiProposalPackage(
            package_id="PACKAGE-R20D",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id=self.event_export_id,
            event=None,
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci daného pracoviště",
                    exposed_group_id=self.group_a.id,
                    severity=RISK_SEVERITY_MODERATE,
                    existing_measures=(
                        AiProposalPackageMeasure(description="Výstražné světlomety"),
                    ),
                    required_measures=(
                        AiProposalPackageMeasure(description="Bezpečná vzdálenost"),
                    ),
                ),
                AiProposalPackageAssessment(
                    exposed_group="Návštěvy a další osoby",
                    exposed_group_id=self.group_b.id,
                    severity=RISK_SEVERITY_SERIOUS,
                    existing_measures=(),
                    required_measures=(
                        AiProposalPackageMeasure(description="Doprovod"),
                        AiProposalPackageMeasure(description="VReflexní vesta"),
                    ),
                ),
            ),
            legal_links=(
                AiProposalPackageLegalLink(reference="Nařízení vlády č. 378/2001 Sb."),
            ),
            reasoning="Doplnění ohrožených skupin.",
        )

    def test_resolve_target_event_name_from_export_map(self) -> None:
        record = self._store_package(self._multi_assessment_package())
        name = resolve_target_event_name(
            package_record_id=record.id,
            target_event_export_id=self.event_export_id,
        )
        self.assertEqual(name, "Přejetí osoby lokomotivou")

    def test_format_package_summary(self) -> None:
        package = self._multi_assessment_package()
        summary = format_package_summary(
            package,
            target_event_name="Přejetí osoby lokomotivou",
        )
        self.assertIn("Doplnění", summary)
        self.assertIn("Přejetí osoby lokomotivou", summary)
        self.assertNotIn(self.event_export_id, summary)
        self.assertIn("Posouzení: 2", summary)
        self.assertIn("Zásady bezpečné práce: 1", summary)
        self.assertIn("Navazující opatření: 3", summary)
        self.assertIn("Právní vazby: 1", summary)

    def test_assessment_section_titles(self) -> None:
        package = self._multi_assessment_package()
        self.assertEqual(
            assessment_section_title(1, package.assessments[0]),
            "Posouzení 1 – Zaměstnanci daného pracoviště",
        )
        self.assertEqual(
            assessment_section_title(2, package.assessments[1]),
            "Posouzení 2 – Návštěvy a další osoby",
        )

    def test_dialog_shows_event_name_not_only_export_id(self) -> None:
        from PySide6.QtWidgets import QDialogButtonBox

        package = self._multi_assessment_package()
        record = self._store_package(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )
        self.assertEqual(
            dialog.target_event_name_label.toPlainText(),
            "Přejetí osoby lokomotivou",
        )
        self.assertEqual(
            dialog.target_event_name_label.toolTip(),
            self.event_export_id,
        )
        self.assertNotEqual(
            dialog.target_event_name_label.toPlainText(),
            self.event_export_id,
        )
        self.assertTrue(dialog.target_event_name_label.isReadOnly())
        self.assertFalse(dialog.target_event_id_label.isVisibleTo(dialog))

        save_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Save)
        assert save_button is not None
        self.assertEqual(save_button.text(), CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON)

    def test_dialog_summary_and_collapsible_assessments(self) -> None:
        from PySide6.QtCore import Qt

        package = self._multi_assessment_package()
        record = self._store_package(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )

        from PySide6.QtWidgets import QGroupBox

        self.assertIn("Posouzení: 2", dialog.summary_label.text())
        self.assertIn("Přejetí osoby lokomotivou", dialog.summary_label.text())
        self.assertIn("Typ:", dialog.summary_label.text())
        summary_boxes = [
            box
            for box in dialog.findChildren(QGroupBox)
            if box.title() == CATALOG_AI_PACKAGE_SUMMARY_TITLE
        ]
        self.assertEqual(len(summary_boxes), 1)

        self.assertEqual(len(dialog._assessment_sections), 2)
        self.assertTrue(dialog._assessment_sections[0].is_expanded())
        self.assertFalse(dialog._assessment_sections[1].is_expanded())
        self.assertEqual(
            dialog._assessment_sections[0].toggle.text(),
            "Posouzení 1 – Zaměstnanci daného pracoviště",
        )
        self.assertEqual(
            dialog._assessment_sections[1].toggle.text(),
            "Posouzení 2 – Návštěvy a další osoby",
        )

        dialog.show()
        dialog._assessment_sections[1].set_expanded(True)
        self.assertTrue(dialog._assessment_sections[1].is_expanded())
        self.assertFalse(dialog._assessment_sections[1].editor.isHidden())
        self.assertTrue(dialog._assessment_sections[1].editor.isVisibleTo(dialog))

        self.assertEqual(
            dialog._scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertTrue(dialog._buttons.isVisibleTo(dialog))
        self.assertGreater(dialog.minimumWidth(), 0)
        self.assertLessEqual(dialog.width(), 900)

    def test_new_event_package_summary_uses_event_name(self) -> None:
        package = AiProposalPackage(
            package_id="PACKAGE-NEW",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád z výšky"),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci daného pracoviště",
                    severity=RISK_SEVERITY_MODERATE,
                ),
            ),
            legal_links=(),
            reasoning="",
        )
        summary = format_package_summary(package)
        self.assertIn("Nová událost: Pád z výšky", summary)
        self.assertIn("Posouzení: 1", summary)


if __name__ == "__main__":
    unittest.main()
