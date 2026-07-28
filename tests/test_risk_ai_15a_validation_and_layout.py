"""RISK-AI-15a: validace cílů (skupina NEBO role) a dvousloupcové rozložení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-15a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_INCORPORATED,
        PACKAGE_STATUS_PENDING,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageEvent,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_PACKAGE_TARGETS_REQUIRED,
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
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        SOURCE_TYPE_ROLE,
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
        assessment_has_targets,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskAi15aTestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("Zaměstnanci AI15a")
        self.role = responsibility_role_service.create_role(name="Profese AI15a")
        self.template = hazard_library_template_service.create_template(
            name="Šablona RISK-AI-15a",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.provider = hazard_catalog_source_peer_review_provider
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            Path(tempfile.mkdtemp()) / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review

    def _package(self) -> AiProposalPackage:
        return AiProposalPackage(
            package_id="PACKAGE-AI15a",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Událost AI15a"),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="",
                    severity=RISK_SEVERITY_MODERATE,
                    conclusion="Závěr",
                    existing_measures=(
                        AiProposalPackageMeasure(description="Zásada"),
                    ),
                    required_measures=(
                        AiProposalPackageMeasure(description="Opatření"),
                    ),
                ),
            ),
            legal_links=(),
            reasoning="test",
        )

    def _store(self, package: AiProposalPackage) -> AiProposalPackageRecord:
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
        self.assertEqual(len(stored), 1)
        return stored[0]

    def test_assessment_has_targets_group_only(self) -> None:
        assessment = AiProposalPackageAssessment(
            exposed_group="Zaměstnanci",
            exposed_group_ids=(self.group.id,),
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="",
        )
        self.assertTrue(assessment_has_targets(assessment))

    def test_assessment_has_targets_role_only(self) -> None:
        assessment = AiProposalPackageAssessment(
            exposed_group="",
            responsibility_role_ids=(self.role.id,),
            severity=RISK_SEVERITY_MODERATE,
            conclusion="",
        )
        self.assertTrue(assessment_has_targets(assessment))

    def test_assessment_has_targets_both(self) -> None:
        assessment = AiProposalPackageAssessment(
            exposed_group="Zaměstnanci",
            exposed_group_ids=(self.group.id,),
            responsibility_role_ids=(self.role.id,),
            severity=RISK_SEVERITY_MODERATE,
            conclusion="",
        )
        self.assertTrue(assessment_has_targets(assessment))

    def test_assessment_has_targets_neither(self) -> None:
        assessment = AiProposalPackageAssessment(
            exposed_group="",
            severity=RISK_SEVERITY_MODERATE,
            conclusion="",
        )
        self.assertFalse(assessment_has_targets(assessment))
        # AI text alone must not pass without explicit selection.
        text_only = AiProposalPackageAssessment(
            exposed_group="Strojvedoucí a opraváři",
            severity=RISK_SEVERITY_MODERATE,
            conclusion="",
        )
        self.assertFalse(assessment_has_targets(text_only))

    def test_save_and_incorporate_share_same_validation(self) -> None:
        package = self._package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([])
        editor.responsibility_roles.set_role_ids([])
        dialog.event_name.setText("Událost AI15a")

        warnings: list[str] = []

        def _capture_warning(_parent, _title, text, *_args, **_kwargs):
            warnings.append(str(text))
            return QMessageBox.Ok

        with patch.object(QMessageBox, "warning", side_effect=_capture_warning):
            dialog._finish_accept(incorporate=False)
            dialog._finish_accept(incorporate=True)

        self.assertEqual(warnings, [CATALOG_AI_PACKAGE_TARGETS_REQUIRED] * 2)
        self.assertIsNone(dialog.get_package())
        dialog.reject()

    def test_save_group_only_passes(self) -> None:
        package = self._package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids([])
        dialog.event_name.setText("Událost AI15a")
        dialog._finish_accept(incorporate=False)
        result = dialog.get_package()
        assert result is not None
        self.assertEqual(result.assessments[0].exposed_group_ids, (self.group.id,))
        self.assertEqual(result.assessments[0].responsibility_role_ids, ())

    def test_save_role_only_passes(self) -> None:
        package = self._package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([])
        editor.responsibility_roles.set_role_ids([self.role.id])
        dialog.event_name.setText("Událost AI15a")
        dialog._finish_accept(incorporate=False)
        result = dialog.get_package()
        assert result is not None
        self.assertEqual(result.assessments[0].exposed_group_ids, ())
        self.assertEqual(result.assessments[0].responsibility_role_ids, (self.role.id,))

    def test_save_both_passes(self) -> None:
        package = self._package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids([self.role.id])
        dialog.event_name.setText("Událost AI15a")
        dialog._finish_accept(incorporate=False)
        result = dialog.get_package()
        assert result is not None
        self.assertEqual(result.assessments[0].exposed_group_ids, (self.group.id,))
        self.assertEqual(result.assessments[0].responsibility_role_ids, (self.role.id,))

    def test_dialog_layout_side_by_side_equal_lists(self) -> None:
        package = self._package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        self.assertEqual(
            editor.exposed_groups.list_widget.minimumHeight(),
            editor.responsibility_roles.list_widget.minimumHeight(),
        )
        self.assertEqual(editor.exposed_groups.list_widget.minimumHeight(), 100)
        dialog.reject()

    def test_incorporate_role_only_creates_assessment(self) -> None:
        package = self._package()
        record = self._store(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([])
        editor.responsibility_roles.set_role_ids([self.role.id])
        dialog.event_name.setText("Událost AI15a")
        dialog._finish_accept(incorporate=True)
        updated = dialog.get_package()
        assert updated is not None
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            updated,
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertGreater(result.new_revision_number, 0)
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_INCORPORATED)

        events = hazard_library_template_event_service.get_for_template(
            self.template.id,
            include_inactive=False,
        )
        created = next(event for event in events if event.name == "Událost AI15a")
        assessments = hazard_library_template_assessment_service.get_for_event(
            created.id,
            include_inactive=False,
        )
        self.assertEqual(len(assessments), 1)
        refs = hazard_library_template_assessment_service.get_target_refs(
            assessments[0].assessment.id,
        )
        ref_keys = {(ref.source_type, ref.source_id) for ref in refs}
        self.assertEqual(ref_keys, {(SOURCE_TYPE_ROLE, self.role.id)})
        self.assertNotIn(SOURCE_TYPE_HAZARD_GROUP, {ref.source_type for ref in refs})


if __name__ == "__main__":
    unittest.main()
