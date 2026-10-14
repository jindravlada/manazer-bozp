"""PERIODICKE-ULOZENI-1 – potvrzení uložení periodických činností."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="periodicke-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.periodicke_cinnosti.constants import TITLE_REQUIRED_MESSAGE
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        PeriodicActivityValidationError,
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )
    from moduly.periodicke_cinnosti.ui.periodic_performance_dialog import (
        PeriodicPerformanceDialog,
    )

CONFIRMATION_TITLE = "Periodické činnosti"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class PeriodickeUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.periodicke_cinnosti.ui.save_confirmation._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def _close(self, dialog) -> None:
        dialog._editor._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Revize hasicích přístrojů")
        dialog.note_edit.setPlainText("uložená poznámka")
        order: list[str] = []
        original = periodic_activity_service.create_activity

        def _create(**kwargs):
            order.append("write")
            return original(**kwargs)

        def _action() -> None:
            with patch.object(periodic_activity_service, "create_activity", side_effect=_create):
                dialog._editor.save_button.click()

        shown = self._run(_action)
        self.assertEqual(order, ["write"])
        self._assert_confirmation(shown)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog.isHidden())
        activity_id = dialog.activity.id
        self._close(dialog)

        reopened = PeriodicActivityDialog(
            activity=periodic_activity_service.get_by_id(activity_id)
        )
        reopened.show()
        self.assertEqual(reopened.title_edit.text(), "Revize hasicích přístrojů")
        self.assertEqual(reopened.note_edit.toPlainText(), "uložená poznámka")
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Jedna změna")
        first = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(first)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        second = self._run(dialog._editor.save_button.click)
        self.assertEqual(second, [])
        direct = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(direct, [])
        self.assertEqual(dialog.title_edit.text(), "Jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Dočasný název")
        dialog.note_edit.setPlainText("rozepsaná poznámka")
        dialog.title_edit.setText("")
        with patch(
            "moduly.periodicke_cinnosti.ui.periodic_activity_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(TITLE_REQUIRED_MESSAGE, warn.call_args.args[2])
        self.assertEqual(dialog.title_edit.text(), "")
        self.assertEqual(dialog.note_edit.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertIsNone(dialog.activity)
        self._close(dialog)

    def test_other_actions_do_not_confirm(self) -> None:
        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Přímé uložení")
        dialog.note_edit.setPlainText("bez tlačítka")
        shown = self._run(lambda: self.assertTrue(dialog._save()))
        self.assertEqual(shown, [])
        stored = periodic_activity_service.get_by_id(dialog.activity.id)
        assert stored is not None
        self.assertEqual(stored.note, "bez tlačítka")
        self._close(dialog)

        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Uložit při zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: self.assertTrue(dialog._editor.request_close()))
        self.assertEqual(shown, [])
        stored = periodic_activity_service.get_by_id(dialog.activity.id)
        assert stored is not None
        self.assertEqual(stored.title, "Uložit při zavření")
        self._close(dialog)

        dialog = PeriodicActivityDialog()
        dialog.show()
        dialog.title_edit.setText("Jen záložka")
        shown = self._run(lambda: dialog.tabs.setCurrentIndex(1))
        self.assertEqual(shown, [])
        self.assertIsNone(dialog.activity)
        self.assertEqual(dialog.title_edit.text(), "Jen záložka")
        self._close(dialog)

    def test_performance_confirms_only_changed_successful_save(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Provedení bez úprav",
            next_due_date=date(2026, 6, 1),
        )
        untouched = PeriodicPerformanceDialog(activity_id=activity.id, activity_title=activity.title)
        untouched.show()
        shown = self._run(untouched._editor.save_button.click)
        self.assertEqual(shown, [])
        self.assertIsNotNone(untouched.occurrence)
        self.assertEqual(len(periodic_activity_service.list_occurrences(activity.id)), 1)
        self._close(untouched)

        changed_activity = periodic_activity_service.create_activity(
            title="Provedení se změnou",
            next_due_date=date(2026, 6, 1),
        )
        dialog = PeriodicPerformanceDialog(
            activity_id=changed_activity.id,
            activity_title=changed_activity.title,
        )
        dialog.show()
        dialog.result_edit.setPlainText("v pořádku")
        shown = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(dialog.isHidden())
        occurrences = periodic_activity_service.list_occurrences(changed_activity.id)
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].result_note, "v pořádku")
        second = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(second, [])
        self.assertEqual(len(periodic_activity_service.list_occurrences(changed_activity.id)), 1)
        self._close(dialog)

        failed_activity = periodic_activity_service.create_activity(
            title="Neúspěšné provedení",
            next_due_date=date(2026, 6, 1),
        )
        failed = PeriodicPerformanceDialog(
            activity_id=failed_activity.id,
            activity_title=failed_activity.title,
        )
        failed.show()
        failed.result_edit.setPlainText("rozepsaný výsledek")
        with (
            patch.object(
                periodic_activity_service,
                "record_performance",
                side_effect=PeriodicActivityValidationError("Nelze uložit provedení."),
            ),
            patch(
                "moduly.periodicke_cinnosti.ui.periodic_performance_dialog.QMessageBox.warning",
            ) as warn,
        ):
            shown = self._run(failed._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertEqual(failed.result_edit.toPlainText(), "rozepsaný výsledek")
        self.assertIsNone(failed.occurrence)
        self.assertEqual(periodic_activity_service.list_occurrences(failed_activity.id), [])
        self._close(failed)
