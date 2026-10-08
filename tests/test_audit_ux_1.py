"""AUDIT-UX-1: potvrzení úspěšného uložení auditu až po dokončení zápisu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-ux-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog, _AUDIT_SAVE_SUCCESS_MESSAGE
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from core.database.session import get_session


def _read_changes(audit_id: int) -> str:
    with get_session() as session:
        row = session.get(Audit, audit_id)
        assert row is not None
        value = row.changes_since_last or ""
        session.expunge(row)
        return value


class AuditUx1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
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

    def _create_audit(self, *, changes: str = "") -> Audit:
        audit = audit_service.create_audit(
            title="UX-1",
            audit_date=date(2026, 4, 15),
            changes_since_last=changes,
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

    def _open_dialog(self, audit: Audit) -> AuditDialog:
        dialog = AuditDialog(audit=audit)
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)
        dialog._capture_baseline()
        return dialog

    def test_successful_save_confirms_only_after_full_persist(self) -> None:
        audit = self._create_audit()
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Uložená změna")
        order: list[str] = []

        real_flush = dialog._deferred.flush
        real_update = audit_service.update_audit

        def _flush(*args, **kwargs):
            order.append("flush")
            return real_flush(*args, **kwargs)

        def _update(*args, **kwargs):
            order.append("update")
            return real_update(*args, **kwargs)

        def _info(*args, **kwargs):
            order.append("info")
            self.assertEqual(_read_changes(audit.id), "Uložená změna")
            self.assertFalse(dialog._is_dirty())
            return QMessageBox.StandardButton.Ok

        with (
            patch.object(dialog._deferred, "flush", _flush),
            patch.object(audit_service, "update_audit", _update),
            patch(
                "moduly.audity.ui.audit_dialog.QMessageBox.information",
                side_effect=_info,
            ) as info,
        ):
            dialog._save_btn.click()

        info.assert_called_once()
        self.assertEqual(info.call_args.args[1], dialog.windowTitle())
        self.assertEqual(info.call_args.args[2], _AUDIT_SAVE_SUCCESS_MESSAGE)
        self.assertEqual(info.call_args.args[2], "Audit byl úspěšně uložen.")
        self.assertEqual(order, ["flush", "update", "info"])
        self.assertFalse(dialog._closing)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog._is_dirty())

    def test_update_failure_shows_error_without_success(self) -> None:
        audit = self._create_audit(changes="Beze změny")
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Nepodaří se")

        with (
            patch.object(
                audit_service,
                "update_audit",
                side_effect=ValueError("uložení selhalo"),
            ),
            patch(
                "moduly.audity.ui.audit_dialog.QMessageBox.information"
            ) as info,
            patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        warning.assert_called_once()
        self.assertIn("uložení selhalo", warning.call_args.args[2])
        self.assertFalse(dialog._closing)
        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_changes(audit.id), "Beze změny")
        self.assertEqual(len(audit_service.get_all()), 1)

    def test_deferred_flush_failure_shows_error_without_success(self) -> None:
        audit = self._create_audit(changes="Odloženo")
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Po flushi")

        with (
            patch.object(
                dialog._deferred,
                "flush",
                side_effect=RuntimeError("flush selhal"),
            ),
            patch.object(audit_service, "update_audit") as update,
            patch(
                "moduly.audity.ui.audit_dialog.QMessageBox.information"
            ) as info,
            patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        update.assert_not_called()
        warning.assert_called_once()
        self.assertIn("Odložené změny se nepodařilo uložit", warning.call_args.args[2])
        self.assertIn("flush selhal", warning.call_args.args[2])
        self.assertFalse(dialog._closing)
        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_changes(audit.id), "Odloženo")

    def test_validation_failure_does_not_confirm(self) -> None:
        audit = self._create_audit()
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Bez týmu")

        with (
            patch.object(
                dialog.commission_widget,
                "validate",
                return_value=(False, "Chybí vedoucí auditor."),
            ),
            patch.object(audit_service, "update_audit") as update,
            patch(
                "moduly.audity.ui.audit_dialog.QMessageBox.information"
            ) as info,
            patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        update.assert_not_called()
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[2], "Chybí vedoucí auditor.")
        self.assertFalse(dialog._closing)

    def test_ok_does_not_save_again_and_second_click_keeps_one_audit(self) -> None:
        audit = self._create_audit(changes="Před")
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Jednou")
        during_dialog: list[int] = []

        real_update = audit_service.update_audit

        def _update(*args, **kwargs):
            return real_update(*args, **kwargs)

        def _info(*args, **kwargs):
            during_dialog.append(update_spy.call_count)
            return QMessageBox.StandardButton.Ok

        with (
            patch.object(audit_service, "update_audit", side_effect=_update) as update_spy,
            patch(
                "moduly.audity.ui.audit_dialog.QMessageBox.information",
                side_effect=_info,
            ),
        ):
            dialog._save_btn.click()
            self.assertEqual(during_dialog, [1])
            self.assertEqual(update_spy.call_count, 1)
            self.assertFalse(dialog._is_dirty())
            self.assertFalse(dialog._closing)

            dialog.history_widget._changes_edit.setPlainText("Podruhé")
            dialog._save_btn.click()

        self.assertEqual(update_spy.call_count, 2)
        self.assertEqual(len(audit_service.get_all()), 1)
        self.assertEqual(audit_service.get_all()[0].id, audit.id)
        self.assertEqual(_read_changes(audit.id), "Podruhé")
        self.assertFalse(dialog._is_dirty())
        self.assertFalse(dialog._closing)

    def test_save_and_close_persists_without_success_dialog(self) -> None:
        audit = self._create_audit(changes="Před zavřením")
        dialog = self._open_dialog(audit)
        dialog.history_widget._changes_edit.setPlainText("Zavřeno")

        with (
            patch("moduly.audity.ui.audit_dialog.QMessageBox.information") as info,
            patch.object(dialog, "_done_accept") as accept,
        ):
            dialog._save_and_close()

        info.assert_not_called()
        accept.assert_called_once()
        self.assertEqual(_read_changes(audit.id), "Zavřeno")


if __name__ == "__main__":
    unittest.main()
