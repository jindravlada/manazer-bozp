"""RISK-AI-15: výběr profesí při AI oponentuře a přímé zapracování balíku."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-15-"))
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
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
    from core.database.session import get_session
    from core.widgets.multi_responsibility_role_selector import (
        MultiResponsibilityRoleSelector,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON,
        CATALOG_AI_PACKAGE_INCORPORATE_BUTTON,
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
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskAi15TestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("Zaměstnanci AI15")
        self.other_group = ensure_exposed_group("Externisté AI15")
        self.role_driver = responsibility_role_service.create_role(name="Strojvedoucí AI15")
        self.role_electrician = responsibility_role_service.create_role(
            name="Elektrikář AI15",
        )
        self.role_repair = responsibility_role_service.create_role(name="Opravář AI15")

        self.template = hazard_library_template_service.create_template(
            name="Šablona RISK-AI-15",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
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

    def _ai_text_package(self) -> AiProposalPackage:
        return AiProposalPackage(
            package_id="PACKAGE-AI15",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Práce na HNKV"),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group=(
                        "Strojvedoucí, elektrikáři a opraváři hnacích kolejových vozidel, "
                        "včetně externích pracovníků"
                    ),
                    severity=RISK_SEVERITY_MODERATE,
                    conclusion="Nutná kontrola OOPP.",
                    existing_measures=(
                        AiProposalPackageMeasure(description="Zásada OOPP"),
                    ),
                    required_measures=(
                        AiProposalPackageMeasure(description="Kontrola OOPP"),
                    ),
                ),
            ),
            legal_links=(),
            reasoning="AI návrh profesí",
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
        self.assertEqual(len(stored), 1)
        return stored[0]

    def test_dialog_has_roles_section_and_incorporate_button(self) -> None:
        package = self._ai_text_package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        self.assertIsInstance(editor.responsibility_roles, MultiResponsibilityRoleSelector)
        self.assertEqual(dialog.incorporate_button.text(), CATALOG_AI_PACKAGE_INCORPORATE_BUTTON)
        save = dialog._buttons.button(dialog._buttons.StandardButton.Save)
        self.assertIsNotNone(save)
        self.assertEqual(save.text(), CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON)
        dialog.reject()

    def test_ai_profession_text_is_not_auto_mapped_to_roles(self) -> None:
        package = self._ai_text_package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        self.assertEqual(editor.responsibility_roles.selected_role_ids(), [])
        dialog.reject()

    def test_add_one_role(self) -> None:
        package = self._ai_text_package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids([self.role_driver.id])
        dialog._finish_accept(incorporate=False)
        result = dialog.get_package()
        assert result is not None
        self.assertEqual(
            result.assessments[0].responsibility_role_ids,
            (self.role_driver.id,),
        )
        self.assertEqual(result.assessments[0].exposed_group_ids, (self.group.id,))

    def test_add_multiple_roles(self) -> None:
        package = self._ai_text_package()
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids(
            [self.role_driver.id, self.role_electrician.id, self.role_repair.id],
        )
        dialog._finish_accept(incorporate=False)
        result = dialog.get_package()
        assert result is not None
        self.assertEqual(
            set(result.assessments[0].responsibility_role_ids),
            {self.role_driver.id, self.role_electrician.id, self.role_repair.id},
        )

    def test_save_roles_and_groups_together(self) -> None:
        package = self._ai_text_package()
        record = self._store_package(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
            review_id=self.review.id,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id, self.other_group.id])
        editor.responsibility_roles.set_role_ids(
            [self.role_driver.id, self.role_electrician.id],
        )
        dialog.event_name.setText("Práce na HNKV")
        dialog._finish_accept(incorporate=False)
        updated = dialog.get_package()
        assert updated is not None
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            updated,
        )
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        loaded = ai_peer_review_service.package_repository.package_from_record(reloaded)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)
        self.assertEqual(
            set(loaded.assessments[0].exposed_group_ids),
            {self.group.id, self.other_group.id},
        )
        self.assertEqual(
            set(loaded.assessments[0].responsibility_role_ids),
            {self.role_driver.id, self.role_electrician.id},
        )

    def test_save_only_keeps_package_pending(self) -> None:
        package = self._ai_text_package()
        record = self._store_package(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids([self.role_driver.id])
        dialog._finish_accept(incorporate=False)
        self.assertFalse(dialog.incorporate_requested())
        updated = dialog.get_package()
        assert updated is not None
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            updated,
        )
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)

    def test_incorporate_from_dialog_saves_roles_and_completes(self) -> None:
        package = self._ai_text_package()
        record = self._store_package(package)
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids(
            [self.role_driver.id, self.role_electrician.id],
        )
        dialog._finish_accept(incorporate=True)
        self.assertTrue(dialog.incorporate_requested())
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
        self.assertTrue(any(event.name == "Práce na HNKV" for event in events))
        created = next(event for event in events if event.name == "Práce na HNKV")
        assessments = hazard_library_template_assessment_service.get_for_event(
            created.id,
            include_inactive=False,
        )
        self.assertEqual(len(assessments), 1)
        refs = hazard_library_template_assessment_service.get_target_refs(
            assessments[0].assessment.id,
        )
        ref_keys = {(ref.source_type, ref.source_id) for ref in refs}
        self.assertIn((SOURCE_TYPE_HAZARD_GROUP, self.group.id), ref_keys)
        self.assertIn((SOURCE_TYPE_ROLE, self.role_driver.id), ref_keys)
        self.assertIn((SOURCE_TYPE_ROLE, self.role_electrician.id), ref_keys)

    def test_widget_save_and_incorporate_removes_from_queue(self) -> None:
        package = self._ai_text_package()
        record = self._store_package(package)
        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget._load_proposals_table()
        pending_before = {
            int(widget.proposals_table.item(row, 0).data(256) or 0)
            for row in range(widget.proposals_table.rowCount())
        }
        # Fallback: count pending packages via service
        pending_packages = [
            item
            for item in ai_peer_review_service.get_packages_for_review(self.review.id)
            if item.status == PACKAGE_STATUS_PENDING
        ]
        self.assertEqual(len(pending_packages), 1)

        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=record.id,
        )
        editor = dialog._assessment_editors[0]
        editor.exposed_groups.set_group_ids([self.group.id])
        editor.responsibility_roles.set_role_ids([self.role_driver.id])
        dialog._finish_accept(incorporate=True)
        updated = dialog.get_package()
        assert updated is not None

        with patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
                hazard_catalog_package_incorporate_service.update_package_payload(
                    record.id,
                    updated,
                )
                widget._select_proposal_row(record.id)
                widget._incorporate_selected_package()

        pending_after = [
            item
            for item in ai_peer_review_service.get_packages_for_review(self.review.id)
            if item.status == PACKAGE_STATUS_PENDING
        ]
        self.assertEqual(pending_after, [])
        widget._load_proposals_table()
        # Queue table should not list incorporated package as pending.
        statuses = []
        for row in range(widget.proposals_table.rowCount()):
            status_item = widget.proposals_table.item(row, 2)
            if status_item is not None:
                statuses.append(status_item.text())
        self.assertNotIn("Čeká", " ".join(statuses) if statuses else "")

    def test_parser_does_not_create_role_ids_from_ai_json(self) -> None:
        package = AiProposalPackage.from_storage_dict(
            {
                "package_id": "PACKAGE-PARSE",
                "package_type": AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                "target_event_export_id": None,
                "event": {"name": "Událost", "description": "", "note": ""},
                "assessments": [
                    {
                        "exposed_group": "Strojvedoucí, elektrikáři",
                        "severity": RISK_SEVERITY_MODERATE,
                        "conclusion": "",
                        "existing_measures": [],
                        "required_measures": [],
                    }
                ],
                "legal_links": [],
                "reasoning": "",
            },
        )
        self.assertEqual(package.assessments[0].responsibility_role_ids, ())
        self.assertIn("Strojvedoucí", package.assessments[0].exposed_group)


if __name__ == "__main__":
    unittest.main()
