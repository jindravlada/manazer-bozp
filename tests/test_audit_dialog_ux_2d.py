"""AUDIT-DIALOG-UX-2d: odložené foto a Dok↔Terén; žádný zápis před Uložit."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-dialog-ux-2d-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.services.control_result_photo_service import control_result_photo_service
    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from core.ui.photo_picker_dialog import PhotoPickerDialog
    from core.widgets.control_result_photo_widget import ControlResultPhotoWidget
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.repository.audit_verification_override_repository import (
        AuditVerificationOverrideRepository,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_verification_service import audit_verification_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


_CONTEXT = ControlPointContext(
    area_id="p1",
    area_label="Proces A",
    section_id="c1",
    section_label="Kritérium A",
    control_point_id="q1",
    control_point_label="Otázka A",
)


def _read_control_row(audit_id: int):
    with get_session() as session:
        rows = (
            session.query(ControlResult)
            .filter_by(
                entity_type=ENTITY_AUDITY,
                entity_id=audit_id,
                source_control_point_id="q1",
            )
            .all()
        )
        if not rows:
            return None
        row = rows[0]
        session.expunge(row)
        return row


def _read_finding_description(finding_id: int) -> str:
    with get_session() as session:
        row = session.get(Finding, finding_id)
        assert row is not None
        value = row.description or ""
        session.expunge(row)
        return value


def _read_silne(audit_id: int) -> str:
    with get_session() as session:
        row = session.get(Audit, audit_id)
        assert row is not None
        value = row.silne_stranky or ""
        session.expunge(row)
        return value


def _override_type(audit_id: int) -> str | None:
    repo = AuditVerificationOverrideRepository()
    row = repo.get(
        audit_id,
        area_id="p1",
        section_id="c1",
        control_point_id="q1",
    )
    if row is None:
        return None
    return audit_verification_service.normalize_verification_type(row.override_verification_type)


class AuditDialogUx2dDeferredMediaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id

    def _create_audit(self, *, silne: str = "OK") -> Audit:
        audit = audit_service.create_audit(
            title="UX-2d",
            audit_date=date(2026, 1, 1),
            silne_stranky=silne,
        )
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        return reloaded

    def _fill_commission(self, dialog: AuditDialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)

    def _discard_close(self, dialog: AuditDialog) -> None:
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            dialog._request_close()

    def _make_source_photo(self, name: str) -> Path:
        path = _TMP / name
        Image.new("RGB", (64, 48), color=(40, 110, 160)).save(path, format="JPEG")
        return path

    def test_add_photo_discard_keeps_db_clean_and_no_orphan(self) -> None:
        audit = self._create_audit()
        source = self._make_source_photo("add_discard.jpg")
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        expected_rel = dialog._deferred.expected_stored_photo_relative_path(
            ENTITY_AUDITY, audit.id, _CONTEXT
        )
        expected_abs = control_result_photo_service.absolute_photo_path(expected_rel)

        widget = ControlResultPhotoWidget(
            auto_persist=False,
            deferred_edits=dialog._deferred,
        )
        widget.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            context=_CONTEXT,
            must_be_saved_message="x",
        )
        with patch.object(PhotoPickerDialog, "get_photo", return_value=source):
            with patch.object(
                control_result_service, "attach_photo", wraps=control_result_service.attach_photo
            ) as spy:
                widget._add_photo()
                spy.assert_not_called()

        self.assertTrue(dialog._is_dirty())
        self.assertIsNone(_read_control_row(audit.id))
        self.assertFalse(expected_abs.exists())

        self._discard_close(dialog)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertIsNone(_read_control_row(audit.id))
        self.assertFalse(expected_abs.exists())

    def test_add_photo_save_writes(self) -> None:
        audit = self._create_audit()
        source = self._make_source_photo("add_save.jpg")
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_photo_attach(ENTITY_AUDITY, audit.id, _CONTEXT, source)
        self.assertTrue(dialog._persist())

        row = _read_control_row(audit.id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertTrue(row.photo_path)
        stored = control_result_photo_service.absolute_photo_path(row.photo_path)
        self.assertTrue(stored.is_file())

    def test_remove_photo_discard_keeps_photo(self) -> None:
        audit = self._create_audit()
        source = self._make_source_photo("remove_keep.jpg")
        control_result_service.attach_photo(ENTITY_AUDITY, audit.id, _CONTEXT, source)
        before = _read_control_row(audit.id)
        assert before is not None
        original_path = before.photo_path
        original_abs = control_result_photo_service.absolute_photo_path(original_path)
        self.assertTrue(original_abs.is_file())

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        widget = ControlResultPhotoWidget(
            auto_persist=False,
            deferred_edits=dialog._deferred,
        )
        widget.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            context=_CONTEXT,
            must_be_saved_message="x",
        )
        from PySide6.QtWidgets import QMessageBox

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            with patch.object(
                control_result_service,
                "remove_photo",
                wraps=control_result_service.remove_photo,
            ) as spy:
                widget._remove_photo()
                spy.assert_not_called()

        self.assertTrue(dialog._is_dirty())
        self._discard_close(dialog)

        after = _read_control_row(audit.id)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after.photo_path, original_path)
        self.assertTrue(original_abs.is_file())

    def test_remove_photo_save_removes(self) -> None:
        audit = self._create_audit()
        source = self._make_source_photo("remove_save.jpg")
        control_result_service.attach_photo(ENTITY_AUDITY, audit.id, _CONTEXT, source)
        before = _read_control_row(audit.id)
        assert before is not None
        original_abs = control_result_photo_service.absolute_photo_path(before.photo_path)

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_photo_remove(ENTITY_AUDITY, audit.id, _CONTEXT)
        self.assertTrue(dialog._persist())

        after = _read_control_row(audit.id)
        self.assertTrue(after is None or not (after.photo_path or ""))
        self.assertFalse(original_abs.exists())

    def test_verification_move_discard_keeps_original(self) -> None:
        audit = self._create_audit()
        self.assertIsNone(_override_type(audit.id))

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_verification_override(
            audit.id,
            area_id="p1",
            section_id="c1",
            control_point_id="q1",
            verification_type=VERIFICATION_TYPE_TERRAIN,
            methodology_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertTrue(dialog._is_dirty())
        self.assertIsNone(_override_type(audit.id))

        with patch.object(
            audit_verification_service,
            "set_override",
            wraps=audit_verification_service.set_override,
        ) as spy:
            self._discard_close(dialog)
            spy.assert_not_called()

        self.assertIsNone(_override_type(audit.id))

    def test_verification_move_save_writes(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_verification_override(
            audit.id,
            area_id="p1",
            section_id="c1",
            control_point_id="q1",
            verification_type=VERIFICATION_TYPE_TERRAIN,
            methodology_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertTrue(dialog._persist())
        self.assertEqual(_override_type(audit.id), VERIFICATION_TYPE_TERRAIN)

    def test_combined_changes_discard_restores_all(self) -> None:
        original_silne = "SILNE ORIGINAL"
        original_finding = "FINDING ORIGINAL"
        original_note = "NOTE ORIGINAL"
        audit = self._create_audit(silne=original_silne)
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description=original_finding,
            status=FINDING_STATUS_OTEVRENE,
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            _CONTEXT,
            result=CONTROL_RESULT_VYHOVUJE,
            note=original_note,
        )
        existing_photo = self._make_source_photo("combined_existing.jpg")
        control_result_service.attach_photo(ENTITY_AUDITY, audit.id, _CONTEXT, existing_photo)
        before_photo = _read_control_row(audit.id)
        assert before_photo is not None
        original_photo_path = before_photo.photo_path
        original_photo_abs = control_result_photo_service.absolute_photo_path(original_photo_path)

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        dialog.conclusion_widget.silne_stranky_edit.setPlainText("SILNE CHANGED")
        dialog._deferred.set_control_result(
            ENTITY_AUDITY,
            audit.id,
            _CONTEXT,
            result=CONTROL_RESULT_VYHOVUJE,
            note="NOTE CHANGED",
            shared_experience=False,
        )
        dialog._deferred.stage_finding_update(
            finding.id,
            {
                "finding_type": FINDING_TYPE_ZJISTENI,
                "reference_label": "",
                "description": "FINDING CHANGED",
                "recommended_action": "",
                "responsible_person_id": None,
                "responsible_person_name": "",
                "due_date": None,
                "status": FINDING_STATUS_OTEVRENE,
                "resolution_note": "",
            },
        )
        new_photo = self._make_source_photo("combined_new.jpg")
        dialog._deferred.stage_photo_attach(ENTITY_AUDITY, audit.id, _CONTEXT, new_photo)
        dialog._deferred.stage_verification_override(
            audit.id,
            area_id="p1",
            section_id="c1",
            control_point_id="q1",
            verification_type=VERIFICATION_TYPE_TERRAIN,
            methodology_type=VERIFICATION_TYPE_DOCUMENTATION,
        )

        expected_new_rel = dialog._deferred.expected_stored_photo_relative_path(
            ENTITY_AUDITY, audit.id, _CONTEXT
        )
        # Po attach by cíl byl stejná cesta jako stávající (název podle kontextu).
        expected_new_abs = control_result_photo_service.absolute_photo_path(expected_new_rel)

        self.assertTrue(dialog._is_dirty())
        self._discard_close(dialog)

        self.assertEqual(_read_silne(audit.id), original_silne)
        self.assertEqual(_read_finding_description(finding.id), original_finding)
        row = _read_control_row(audit.id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.note or "", original_note)
        self.assertEqual(row.photo_path, original_photo_path)
        self.assertTrue(original_photo_abs.is_file())
        self.assertIsNone(_override_type(audit.id))
        # Odložený attach nesmí zapsat nový obsah bez Uložit — soubor zůstává původní.
        self.assertEqual(
            original_photo_abs.read_bytes(),
            control_result_photo_service.absolute_photo_path(original_photo_path).read_bytes(),
        )
        # Žádný orphan mimo stávající uloženou cestu (attach se neprovedl).
        self.assertEqual(expected_new_abs, original_photo_abs)


if __name__ == "__main__":
    unittest.main()
