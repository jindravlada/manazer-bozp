"""UX-SAVE-1b – skutečné Uložit/Zrušit v editoru katalogu zdrojů rizik."""

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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
        HazardLibraryTemplateWorkingCopy,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryUxSave1bTestCase(unittest.TestCase):
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
            name=f"UX-SAVE-1b {id(self)}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

    def _patch_info(self):
        from PySide6.QtWidgets import QMessageBox

        return patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        )

    def test_save_persists_and_bumps_once(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._content_store is not None
        dialog._content_store.create_event(
            template_id=self.template.id,
            name="Událost A",
        )
        dialog._content_store.create_event(
            template_id=self.template.id,
            name="Událost B",
        )
        dialog._update_save_enabled()
        self.assertTrue(dialog.is_dirty())
        self.assertTrue(dialog.save_button.isEnabled())

        with self._patch_info():
            self.assertTrue(dialog._save_all())

        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.save_button.isEnabled())
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 2)
        with get_session() as session:
            revisions = list(
                session.query(HazardLibraryTemplateRevision).filter_by(
                    template_id=self.template.id,
                ),
            )
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0].revision_number, 2)

    def test_cancel_discards_without_revision(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._content_store is not None
        dialog._content_store.create_event(
            template_id=self.template.id,
            name="Dočasná",
        )
        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)
        self.assertEqual(
            hazard_library_template_event_service.get_for_template(self.template.id),
            [],
        )

    def test_close_prompt_save_discard_stay(self) -> None:
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QMessageBox

        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._content_store is not None
        dialog._content_store.create_event(
            template_id=self.template.id,
            name="Dirty event",
        )

        with patch.object(dialog, "_prompt_unsaved_close", return_value="stay"):
            event = QCloseEvent()
            dialog.closeEvent(event)
            self.assertTrue(event.isAccepted() is False or not event.isAccepted())
            self.assertTrue(dialog.is_dirty())

        with patch.object(dialog, "_prompt_unsaved_close", return_value="discard"):
            event = QCloseEvent()
            dialog.closeEvent(event)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )

        dialog = HazardLibraryTemplateDialog(template=self.template)
        assert dialog._content_store is not None
        dialog._content_store.create_event(
            template_id=self.template.id,
            name="Saved on close",
        )
        with self._patch_info():
            with patch.object(dialog, "_prompt_unsaved_close", return_value="save"):
                event = QCloseEvent()
                dialog.closeEvent(event)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            1,
        )

    def test_ai_incorporate_deferred_until_save(self) -> None:
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        package = AiProposalPackage(
            package_id="pkg-1",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            reasoning="důvod",
            event=AiProposalPackageEvent(
                name="AI událost",
                description="popis",
                note="",
            ),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Zaměstnanci daného pracoviště",
                    exposed_group_ids=(self.group.id,),
                    severity=RISK_SEVERITY_MODERATE,
                    conclusion="závěr",
                    existing_measures=(
                        AiProposalPackageMeasure(description="Existující", note=""),
                    ),
                    required_measures=(
                        AiProposalPackageMeasure(description="Potřebné", note=""),
                    ),
                ),
            ),
            legal_links=(),
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(updated.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        result = dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.new_revision_number, 0)
        self.assertTrue(dialog.is_dirty())

        with get_session() as session:
            pending = session.get(AiProposalPackageRecord, record.id)
            assert pending is not None
            self.assertEqual(pending.status, PACKAGE_STATUS_PENDING)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )

        with self._patch_info():
            self.assertTrue(dialog._save_all())

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "AI událost")
        with get_session() as session:
            saved = session.get(AiProposalPackageRecord, record.id)
            assert saved is not None
            self.assertEqual(saved.status, PACKAGE_STATUS_INCORPORATED)

    def test_ai_cancel_keeps_package_pending(self) -> None:
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        package = AiProposalPackage(
            package_id="pkg-cancel",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            reasoning="důvod",
            event=AiProposalPackageEvent(name="Zrušená AI", description="", note=""),
            assessments=(),
            legal_links=(),
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        record = ai_peer_review_service.get_packages_for_review(updated.id)[0]

        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        dialog._discard_working_copy()
        dialog._closing = True
        dialog.reject()

        with get_session() as session:
            pending = session.get(AiProposalPackageRecord, record.id)
            assert pending is not None
            self.assertEqual(pending.status, PACKAGE_STATUS_PENDING)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )

    def test_commit_rollback_on_error(self) -> None:
        wc = HazardLibraryTemplateWorkingCopy.load(self.template.id)
        wc.create_event(template_id=self.template.id, name="Rollback event")
        with patch(
            "moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy."
            "HazardLibraryTemplateWorkingCopy._commit_events",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                wc.commit()

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)
        self.assertEqual(
            len(hazard_library_template_event_service.get_for_template(self.template.id)),
            0,
        )
        with get_session() as session:
            revisions = list(
                session.query(HazardLibraryTemplateRevision).filter_by(
                    template_id=self.template.id,
                ),
            )
        self.assertEqual(revisions, [])

    def test_save_disabled_when_clean(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.save_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
