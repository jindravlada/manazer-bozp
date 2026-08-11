"""AUDIT-DIALOG-UX-2b: Zavřít/Neukládat nesmí zapsat hlavní údaje auditu do DB."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-dialog-ux-2b-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _read_silne_in_fresh_session(audit_id: int) -> str:
    """Načte silne_stranky v úplně nové session (bez identity map)."""
    with get_session() as session:
        row = session.get(Audit, audit_id)
        assert row is not None
        value = row.silne_stranky or ""
        session.expunge(row)
        return value


class AuditDialogUx2DiscardDbTestCase(unittest.TestCase):
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

    def _create_audit(self, *, silne: str) -> Audit:
        audit = audit_service.create_audit(
            title="UX-2b",
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

    def test_discard_via_zavrit_keeps_original_in_new_session(self) -> None:
        original = "PŮVODNÍ TEXT SILNÝCH STRÁNEK"
        audit = self._create_audit(silne=original)
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        dialog.conclusion_widget.silne_stranky_edit.setPlainText("ZMĚNĚNÝ TEXT")
        self.assertTrue(dialog._is_dirty())

        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            with patch.object(
                audit_service,
                "update_audit",
                wraps=audit_service.update_audit,
            ) as spy_update:
                dialog._request_close()
                spy_update.assert_not_called()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(_read_silne_in_fresh_session(audit.id), original)
        self.assertEqual(
            (audit_service.get_by_id(audit.id).silne_stranky or ""),
            original,
        )

    def test_discard_via_escape_keeps_original(self) -> None:
        original = "ESCAPE ORIGINAL"
        audit = self._create_audit(silne=original)
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("ESCAPE CHANGED")
        self.assertTrue(dialog._is_dirty())

        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            with patch.object(
                audit_service,
                "update_audit",
                wraps=audit_service.update_audit,
            ) as spy_update:
                dialog.reject()
                spy_update.assert_not_called()

        self.assertEqual(_read_silne_in_fresh_session(audit.id), original)

    def test_discard_via_close_event_keeps_original(self) -> None:
        original = "X ORIGINAL"
        audit = self._create_audit(silne=original)
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("X CHANGED")
        self.assertTrue(dialog._is_dirty())

        event = QCloseEvent()
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            with patch.object(
                audit_service,
                "update_audit",
                wraps=audit_service.update_audit,
            ) as spy_update:
                dialog.closeEvent(event)
                spy_update.assert_not_called()

        self.assertTrue(event.isAccepted())
        self.assertEqual(_read_silne_in_fresh_session(audit.id), original)

    def test_save_keep_open_writes_to_db(self) -> None:
        audit = self._create_audit(silne="PŘED ULOŽENÍM")
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("PO ULOŽENÍ")
        self.assertTrue(dialog._persist())
        self.assertFalse(dialog._is_dirty())
        self.assertEqual(_read_silne_in_fresh_session(audit.id), "PO ULOŽENÍ")

    def test_accept_alone_does_not_write(self) -> None:
        original = "ACCEPT NESMÍ ULOŽIT"
        audit = self._create_audit(silne=original)
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("ACCEPT CHANGED")
        with patch.object(
            audit_service,
            "update_audit",
            wraps=audit_service.update_audit,
        ) as spy_update:
            dialog.accept()
            spy_update.assert_not_called()
        self.assertEqual(_read_silne_in_fresh_session(audit.id), original)

    def test_no_auto_dirty_tracking(self) -> None:
        text = Path("moduly/audity/ui/audit_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("install_auto_dirty_tracking", text)
        self.assertNotIn("EditorDialogController(", text)

    def test_dirty_prompt_save_uses_action_role_not_accept(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        from core.widgets.editor_dialog_controller import confirm_unsaved_editor_close

        roles: list[QMessageBox.ButtonRole] = []

        original_add = QMessageBox.addButton

        def _capture(self, *args, **kwargs):
            button = original_add(self, *args, **kwargs)
            if len(args) >= 2 and isinstance(args[1], QMessageBox.ButtonRole):
                roles.append(args[1])
            elif "role" in kwargs:
                roles.append(kwargs["role"])
            return button

        with patch.object(QMessageBox, "addButton", _capture):
            with patch.object(QMessageBox, "exec", return_value=0):
                confirm_unsaved_editor_close(None, title="t")

        self.assertTrue(roles)
        self.assertNotIn(QMessageBox.ButtonRole.AcceptRole, roles)


if __name__ == "__main__":
    unittest.main()
