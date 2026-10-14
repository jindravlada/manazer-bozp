"""ROCNI-PLAN-ULOZENI-1 – potvrzení uložení v Ročním plánu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="rocni-plan-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.rocni_plan.constants import TITLE_REQUIRED_MESSAGE
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.rocni_plan.ui.yearly_plan_item_dialog import YearlyPlanItemDialog
    from moduly.rocni_plan.ui.yearly_plan_move_dialog import YearlyPlanMoveDialog

CONFIRMATION_TITLE = "Roční plán"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class RocniPlanUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.rocni_plan.ui.save_confirmation._exec_message_box",
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
        dialog = YearlyPlanItemDialog(default_year=2026, default_month=4)
        dialog.show()
        dialog.title_edit.setText("Školení BOZP")
        dialog.note_edit.setPlainText("uložená poznámka")
        order: list[str] = []
        original = yearly_plan_service.create

        def _create(**kwargs):
            order.append("write")
            return original(**kwargs)

        def _action() -> None:
            with patch.object(yearly_plan_service, "create", side_effect=_create):
                dialog._editor.save_button.click()

        shown = self._run(_action)
        self.assertEqual(order, ["write"])
        self._assert_confirmation(shown)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog.isHidden())
        item_id = dialog.item.id
        self._close(dialog)

        reopened = YearlyPlanItemDialog(item=yearly_plan_service.get_by_id(item_id))
        reopened.show()
        self.assertEqual(reopened.title_edit.text(), "Školení BOZP")
        self.assertEqual(reopened.note_edit.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.year_combo.currentData(), 2026)
        self.assertEqual(reopened.month_combo.currentData(), 4)
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = YearlyPlanItemDialog(default_year=2026, default_month=5)
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
        dialog = YearlyPlanItemDialog(default_year=2026, default_month=6)
        dialog.show()
        dialog.title_edit.setText("Dočasný název")
        dialog.note_edit.setPlainText("rozepsaná poznámka")
        dialog.title_edit.setText("")
        with patch(
            "moduly.rocni_plan.ui.yearly_plan_item_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(TITLE_REQUIRED_MESSAGE, warn.call_args.args[2])
        self.assertEqual(dialog.title_edit.text(), "")
        self.assertEqual(dialog.note_edit.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertIsNone(dialog.item)
        self._close(dialog)

    def test_other_actions_do_not_confirm(self) -> None:
        dialog = YearlyPlanItemDialog(default_year=2026, default_month=7)
        dialog.show()
        dialog.title_edit.setText("Přímé uložení")
        dialog.note_edit.setPlainText("bez tlačítka")
        shown = self._run(lambda: self.assertTrue(dialog._save()))
        self.assertEqual(shown, [])
        stored = yearly_plan_service.get_by_id(dialog.item.id)
        assert stored is not None
        self.assertEqual(stored.note, "bez tlačítka")
        self._close(dialog)

        dialog = YearlyPlanItemDialog(default_year=2026, default_month=8)
        dialog.show()
        dialog.title_edit.setText("Uložit při zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: self.assertTrue(dialog._editor.request_close()))
        self.assertEqual(shown, [])
        stored = yearly_plan_service.get_by_id(dialog.item.id)
        assert stored is not None
        self.assertEqual(stored.title, "Uložit při zavření")
        self._close(dialog)

        dialog = YearlyPlanItemDialog(default_year=2026, default_month=9)
        dialog.show()
        dialog.title_edit.setText("Jen záložka")
        shown = self._run(lambda: dialog.tabs.setCurrentIndex(1))
        self.assertEqual(shown, [])
        self.assertIsNone(dialog.item)
        self.assertEqual(dialog.title_edit.text(), "Jen záložka")
        self._close(dialog)

    def test_move_dialog_save_closes_without_confirmation(self) -> None:
        dialog = YearlyPlanMoveDialog(from_year=2026, from_month=3)
        dialog.show()
        dialog.month_combo.setCurrentIndex(dialog.month_combo.findData(11))
        save_button = dialog.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Save
        )
        assert save_button is not None
        shown = self._run(save_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_year(), 2026)
        self.assertEqual(dialog.selected_month(), 11)
        dialog.close()
