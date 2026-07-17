"""UX-SAVE-1b.1 – odložené ukládání AI balíků v katalogu."""

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
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_MANUAL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.catalog_editor_session import (
        SESSION_PACKAGE_PENDING,
        SESSION_PACKAGE_STAGED,
        CatalogEditorSession,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryUxSave1b1TestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci daného pracoviště")
        self.template = hazard_library_template_service.create_template(
            name=f"UX-SAVE-1b.1 {id(self)}",
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

    def _patch_info(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        )

    def _new_event_package(
        self,
        *,
        package_id: str,
        name: str,
        with_assessment: bool = True,
    ) -> AiProposalPackage:
        assessments = ()
        if with_assessment:
            assessments = (
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci daného pracoviště",
                    exposed_group_ids=(self.group.id,),
                    severity=RISK_SEVERITY_MODERATE,
                    conclusion="závěr",
                    existing_measures=(
                        AiProposalPackageMeasure(description="Existující", note=""),
                    ),
                    required_measures=(),
                ),
            )
        return AiProposalPackage(
            package_id=package_id,
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            reasoning="důvod",
            event=AiProposalPackageEvent(name=name, description="popis", note=""),
            assessments=assessments,
            legal_links=(),
        )

    def _count_packages(self) -> int:
        with get_session() as session:
            return len(list(session.query(AiProposalPackageRecord).all()))

    def test_import_cancel_does_not_create_package(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        dialog._editor_session.import_packages(
            review_id=self.review.id,
            source_type=hazard_catalog_source_peer_review_provider.source_type,
            packages=[self._new_event_package(package_id="imp-1", name="Import A")],
            response_text="{}",
            ai_model="Test",
        )
        self.assertEqual(self._count_packages(), 0)
        self.assertEqual(len(dialog._editor_session.list_pending_packages()), 1)

        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        self.assertEqual(self._count_packages(), 0)

    def test_import_save_creates_package(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        dialog._editor_session.import_packages(
            review_id=self.review.id,
            source_type=hazard_catalog_source_peer_review_provider.source_type,
            packages=[self._new_event_package(package_id="imp-2", name="Import B")],
            response_text="{}",
            ai_model="Test",
        )
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        self.assertEqual(self._count_packages(), 1)
        with get_session() as session:
            record = session.query(AiProposalPackageRecord).one()
            self.assertEqual(record.status, PACKAGE_STATUS_PENDING)
            package = ai_peer_review_service.package_repository.package_from_record(record)
            self.assertEqual(package.event_name, "Import B")

    def test_edit_package_cancel_discards_payload(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[self._new_event_package(package_id="edit-1", name="Původní")],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        item = dialog._editor_session.get_package(record.id)
        assert item is not None
        edited = self._new_event_package(package_id="edit-1", name="Upravený")
        dialog._editor_session.update_package(record.id, edited)

        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        package = ai_peer_review_service.package_repository.package_from_record(reloaded)
        self.assertEqual(package.event_name, "Původní")

    def test_edit_package_save_persists_payload(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[
                self._new_event_package(
                    package_id="edit-2",
                    name="Původní",
                    with_assessment=True,
                ),
            ],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        edited = AiProposalPackage(
            package_id="edit-2",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            reasoning="důvod",
            event=AiProposalPackageEvent(name="Upravený", description="popis", note=""),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci daného pracoviště",
                    exposed_groups=(
                        "Zaměstnanci daného pracoviště",
                        "Nová osoba v balíku",
                    ),
                    exposed_group_ids=(self.group.id,),
                    severity=RISK_SEVERITY_MODERATE,
                    conclusion="závěr",
                    existing_measures=(
                        AiProposalPackageMeasure(description="Existující", note=""),
                    ),
                    required_measures=(),
                ),
            ),
            legal_links=(),
        )
        dialog._editor_session.update_package(record.id, edited)
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        package = ai_peer_review_service.package_repository.package_from_record(reloaded)
        self.assertEqual(package.event_name, "Upravený")
        self.assertIn("Nová osoba v balíku", package.assessments[0].exposed_groups)

    def test_incorporate_cancel_keeps_pending(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[self._new_event_package(package_id="inc-1", name="AI událost")],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        assert dialog._editor_session is not None
        staged = dialog._editor_session.get_package(record.id)
        assert staged is not None
        self.assertEqual(staged.session_status, SESSION_PACKAGE_STAGED)
        self.assertEqual(len(dialog._editor_session.list_pending_packages()), 0)

        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )
        template = hazard_library_template_service.get_by_id(self.template.id)
        assert template is not None
        self.assertEqual(template.version_number, 1)

        dialog2 = HazardLibraryTemplateDialog(template=template)
        assert dialog2._editor_session is not None
        self.assertEqual(len(dialog2._editor_session.list_pending_packages()), 1)
        self.assertIsNotNone(dialog2._editor_session.get_package(record.id))

    def test_incorporate_save_marks_incorporated(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[self._new_event_package(package_id="inc-2", name="AI událost 2")],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_INCORPORATED)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        template = hazard_library_template_service.get_by_id(self.template.id)
        assert template is not None
        self.assertEqual(template.version_number, 2)

    def test_staged_package_removed_from_pending_list(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[self._new_event_package(package_id="list-1", name="Seznam")],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]
        session = CatalogEditorSession.load(self.template.id)
        self.assertEqual(len(session.list_pending_packages()), 1)
        hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
            session.content,
            template_id=self.template.id,
            package_record_id=record.id,
            editor_session=session,
        )
        pending = session.list_pending_packages()
        self.assertEqual(pending, [])
        for item in session.packages.values():
            self.assertIsNotNone(item.package)
            if item.local_id == record.id:
                self.assertEqual(item.session_status, SESSION_PACKAGE_STAGED)

    def test_multiple_imports_and_incorporate_single_revision(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        dialog._editor_session.import_packages(
            review_id=self.review.id,
            source_type=hazard_catalog_source_peer_review_provider.source_type,
            packages=[
                self._new_event_package(package_id="m1", name="Multi 1"),
                self._new_event_package(package_id="m2", name="Multi 2"),
            ],
            response_text="{}",
            ai_model="Test",
        )
        pending = dialog._editor_session.list_pending_packages()
        self.assertEqual(len(pending), 2)
        for item in pending:
            dialog._incorporate_package_into_working_copy(
                template_id=self.template.id,
                package_record_id=item.local_id,
            )
        self.assertEqual(len(dialog._editor_session.list_pending_packages()), 0)
        with self._patch_info():
            self.assertTrue(dialog._save_all())

        template = hazard_library_template_service.get_by_id(self.template.id)
        assert template is not None
        self.assertEqual(template.version_number, 2)
        with get_session() as session:
            revisions = list(
                session.query(HazardLibraryTemplateRevision).filter_by(
                    template_id=self.template.id,
                ),
            )
            packages = list(session.query(AiProposalPackageRecord).all())
        self.assertEqual(len(revisions), 1)
        self.assertEqual(len(packages), 2)
        self.assertTrue(all(p.status == PACKAGE_STATUS_INCORPORATED for p in packages))
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            2,
        )

    def test_commit_rollback_packages_and_catalog(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        dialog._editor_session.import_packages(
            review_id=self.review.id,
            source_type=hazard_catalog_source_peer_review_provider.source_type,
            packages=[self._new_event_package(package_id="rb-1", name="Rollback")],
            response_text="{}",
            ai_model="Test",
        )
        item = dialog._editor_session.list_pending_packages()[0]
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=item.local_id,
        )
        with patch.object(
            CatalogEditorSession,
            "_reload_packages_after_commit",
            side_effect=RuntimeError("boom after write"),
        ):
            # Force failure inside commit after content write path via _commit_events.
            pass
        with patch(
            "moduly.rizeni_rizik.sluzby.catalog_editor_session."
            "HazardLibraryTemplateWorkingCopy._commit_events",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                dialog._editor_session.commit()

        self.assertEqual(self._count_packages(), 0)
        template = hazard_library_template_service.get_by_id(self.template.id)
        assert template is not None
        self.assertEqual(template.version_number, 1)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )

    def test_pending_list_rows_have_valid_objects(self) -> None:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[self._new_event_package(package_id="valid-1", name="Validní")],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(stored.id)[0]
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._editor_session is not None
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        for item in dialog._editor_session.list_pending_packages():
            self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)
            self.assertIsNotNone(dialog._editor_session.get_package(item.local_id))
        # staged balík není v pending seznamu, ale objekt ve session existuje
        staged = dialog._editor_session.get_package(record.id)
        assert staged is not None
        self.assertEqual(staged.session_status, SESSION_PACKAGE_STAGED)


if __name__ == "__main__":
    unittest.main()
