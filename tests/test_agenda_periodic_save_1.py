"""ÚKOL 03 – sjednocení ukládání formuláře periodické činnosti."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

_TMP = Path(tempfile.mkdtemp(prefix="agenda-periodic-save-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.attachment_service import attachment_service
    from core.widgets.editor_dialog_controller import (
        EDITOR_CLOSE_LABEL,
        EDITOR_SAVE_LABEL,
        EDITOR_UNSAVED_DISCARD_LABEL,
        confirm_unsaved_editor_close,
    )
    from moduly.periodicke_cinnosti.constants import (
        COL_TITLE,
        DIALOG_TITLE_EDIT,
        ENTITY_PERIODIC_OCCURRENCE,
        NEXT_FROM_PLANNED,
        TITLE_REQUIRED_MESSAGE,
        UNIT_DAYS,
        UNIT_MONTHS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        PeriodicActivityValidationError,
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activities_tab import PeriodicActivitiesTab
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
        _SAVE_CLOSE_LABEL,
        _UNSAVED_ABORT_LABEL,
    )
    from moduly.periodicke_cinnosti.ui.save_confirmation import (
        _SAVE_CONFIRMATION_TEXT,
        _SAVE_CONFIRMATION_TITLE,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import list_periodic_rows_for_month

_PROMPT = "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
_INFO = "moduly.periodicke_cinnosti.ui.save_confirmation._exec_message_box"


class AgendaPeriodicSave1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _open(self, activity=None) -> PeriodicActivityDialog:
        dialog = PeriodicActivityDialog(activity=activity)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: PeriodicActivityDialog) -> None:
        dialog._editor._closing = True
        dialog.close()
        dialog.deleteLater()

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(_INFO, side_effect=_exec):
            action()
        return shown

    def _labels(self, dialog: PeriodicActivityDialog) -> list[str]:
        layout = dialog.layout()
        footer = layout.itemAt(layout.count() - 1).layout()
        labels = []
        for index in range(footer.count()):
            widget = footer.itemAt(index).widget()
            if isinstance(widget, QPushButton) and widget.isVisible():
                labels.append(widget.text())
        return labels

    def _create(self, title: str = "Původní činnost"):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=date(2026, 6, 1),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=14,
            notify_unit=UNIT_DAYS,
            next_from=NEXT_FROM_PLANNED,
            note="původní poznámka",
            active=True,
        )

    def test_new_and_existing_share_three_buttons(self) -> None:
        fresh = self._open()
        existing = self._open(self._create())
        try:
            for dialog in (fresh, existing):
                self.assertEqual(
                    self._labels(dialog),
                    [EDITOR_SAVE_LABEL, _SAVE_CLOSE_LABEL, EDITOR_CLOSE_LABEL],
                )
                layout = dialog.layout()
                footer = layout.itemAt(layout.count() - 1).layout()
                stretch_at = next(
                    index
                    for index in range(footer.count())
                    if footer.itemAt(index).spacerItem() is not None
                )
                self.assertLess(stretch_at, footer.indexOf(dialog._editor.save_button))
                self.assertLess(
                    footer.indexOf(dialog._editor.save_button),
                    footer.indexOf(dialog._save_close_btn),
                )
                self.assertLess(
                    footer.indexOf(dialog._save_close_btn),
                    footer.indexOf(dialog._editor.close_button),
                )
        finally:
            self._close(fresh)
            self._close(existing)

    def test_save_confirms_stays_open_and_second_save_does_not_duplicate(self) -> None:
        dialog = self._open()
        try:
            dialog.title_edit.setText("Jedna činnost")
            dialog.note_edit.setPlainText("poznámka")
            dialog.calendar_interval.setValue(60)
            first = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0].windowTitle(), _SAVE_CONFIRMATION_TITLE)
            self.assertEqual(first[0].text(), _SAVE_CONFIRMATION_TEXT)
            self.assertEqual(first[0].icon(), QMessageBox.Icon.Information)
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._editor.is_new)
            self.assertFalse(dialog._editor.is_dirty())
            self.assertEqual(dialog.windowTitle(), DIALOG_TITLE_EDIT)
            activity_id = int(dialog.activity.id)
            self.assertFalse(dialog._editor.save_button.isEnabled())
            self.assertFalse(dialog._save_close_btn.isEnabled())

            dialog.title_edit.setText("Jedna činnost upravena")
            second = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(second), 1)
            self.assertEqual(dialog.activity.id, activity_id)
        finally:
            self._close(dialog)

        matches = [
            item
            for item in periodic_activity_service.get_all()
            if item.id == activity_id or (item.title or "").startswith("Jedna činnost")
        ]
        self.assertEqual(len(matches), 1)
        stored = matches[0]
        self.assertEqual(stored.title, "Jedna činnost upravena")
        self.assertEqual(stored.note, "poznámka")
        self.assertIsNone(stored.next_due_date)
        self.assertEqual(stored.calendar_interval_months, 60)

        reopened = self._open(periodic_activity_service.get_by_id(activity_id))
        try:
            self.assertEqual(reopened.title_edit.text(), "Jedna činnost upravena")
            self.assertEqual(reopened.calendar_interval.value(), 60)
            self.assertFalse(reopened._editor.is_dirty())
            self.assertFalse(reopened._editor.is_new)
        finally:
            self._close(reopened)

    def test_save_and_close_without_confirmation(self) -> None:
        activity = self._create()
        dialog = self._open(activity)
        dialog.note_edit.setPlainText("zapsáno a zavřeno")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.note, "zapsáno a zavřeno")
        self.assertEqual(stored.repeat_every, 1)
        self.assertEqual(stored.next_due_date, date(2026, 6, 1))
        self.assertIsNone(stored.calendar_start_year)
        dialog.deleteLater()

    def test_failed_save_keeps_window_and_draft(self) -> None:
        activity = self._create(title="Platná")
        dialog = self._open(activity)
        try:
            dialog.title_edit.setText("Rozepsaná")
            with (
                patch.object(
                    periodic_activity_service,
                    "update_activity",
                    side_effect=PeriodicActivityValidationError("Nelze uložit."),
                ),
                patch(
                    "moduly.periodicke_cinnosti.ui.periodic_activity_dialog.QMessageBox.warning",
                ) as warning,
            ):
                shown = self._run(dialog._save_close_btn.click)
            self.assertEqual(shown, [])
            warning.assert_called()
            self.assertTrue(dialog.isVisible())
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertEqual(dialog.title_edit.text(), "Rozepsaná")
            self.assertTrue(dialog._editor.is_dirty())
        finally:
            self._close(dialog)
        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.title, "Platná")

        fresh = self._open()
        try:
            fresh.note_edit.setPlainText("bez názvu")
            with patch(
                "moduly.periodicke_cinnosti.ui.periodic_activity_dialog.QMessageBox.warning",
            ) as warning:
                shown = self._run(fresh._editor.save_button.click)
            self.assertEqual(shown, [])
            warning.assert_called_once()
            self.assertIn(TITLE_REQUIRED_MESSAGE, warning.call_args.args[2])
            self.assertIsNone(fresh.activity)
            self.assertTrue(fresh.isVisible())
        finally:
            self._close(fresh)

    def test_close_discard_and_back(self) -> None:
        activity = self._create(title="Ponechat")
        dialog = self._open(activity)
        try:
            dialog.title_edit.setText("Nemá se zapsat")
            with patch(_PROMPT, return_value="discard") as prompt:
                dialog._editor.close_button.click()
            prompt.assert_called_once()
            self.assertEqual(
                prompt.call_args.kwargs.get("abort_label"),
                _UNSAVED_ABORT_LABEL,
            )
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        finally:
            if dialog.isVisible():
                self._close(dialog)
        self.assertEqual(
            periodic_activity_service.get_by_id(activity.id).title,
            "Ponechat",
        )

        again = self._open(periodic_activity_service.get_by_id(activity.id))
        try:
            again.note_edit.setPlainText("zůstat ve formuláři")
            with patch(_PROMPT, return_value="cancel"):
                again._editor.close_button.click()
            self.assertTrue(again.isVisible())
            self.assertEqual(again.note_edit.toPlainText(), "zůstat ve formuláři")
            self.assertEqual(
                periodic_activity_service.get_by_id(activity.id).note,
                "původní poznámka",
            )
        finally:
            self._close(again)

    def test_prompt_save_closes_without_confirmation(self) -> None:
        activity = self._create()
        dialog = self._open(activity)
        dialog.title_edit.setText("Z dotazu")
        with patch(_PROMPT, return_value="save"):
            shown = self._run(dialog._editor.close_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(
            periodic_activity_service.get_by_id(activity.id).title,
            "Z dotazu",
        )
        dialog.deleteLater()

    def test_escape_and_system_close_match_close_button(self) -> None:
        activity = self._create(title="Křížek")
        dialog = self._open(activity)
        dialog.title_edit.setText("Z křížku ne")
        event = QCloseEvent()
        with patch(_PROMPT, return_value="discard"):
            dialog._editor.eventFilter(dialog, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(
            periodic_activity_service.get_by_id(activity.id).title,
            "Křížek",
        )
        dialog.deleteLater()

        dialog = self._open(periodic_activity_service.get_by_id(activity.id))
        try:
            dialog.title_edit.setText("Escape zpět")
            key = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            )
            with patch(_PROMPT, return_value="cancel"):
                handled = dialog._editor.eventFilter(dialog, key)
            self.assertTrue(handled)
            self.assertTrue(dialog.isVisible())
            self.assertEqual(dialog.title_edit.text(), "Escape zpět")
        finally:
            self._close(dialog)

        dialog = self._open(periodic_activity_service.get_by_id(activity.id))
        dialog.note_edit.setPlainText("Uloženo escapem")
        key = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch(_PROMPT, return_value="save"):
            shown = self._run(lambda: dialog._editor.eventFilter(dialog, key))
        self.assertEqual(shown, [])
        self.assertEqual(
            periodic_activity_service.get_by_id(activity.id).note,
            "Uloženo escapem",
        )
        dialog.deleteLater()

    def test_unsaved_prompt_labels(self) -> None:
        with patch(
            "core.widgets.editor_dialog_controller.QMessageBox"
        ) as mock_box_cls:
            instance = mock_box_cls.return_value
            buttons = [MagicMock(), MagicMock(), MagicMock()]
            instance.addButton.side_effect = buttons
            instance.clickedButton.return_value = buttons[2]
            decision = confirm_unsaved_editor_close(
                None,
                title=DIALOG_TITLE_EDIT,
                abort_label=_UNSAVED_ABORT_LABEL,
            )
        self.assertEqual(decision, "cancel")
        labels = [call.args[0] for call in instance.addButton.call_args_list]
        self.assertEqual(
            labels,
            [EDITOR_SAVE_LABEL, EDITOR_UNSAVED_DISCARD_LABEL, _UNSAVED_ABORT_LABEL],
        )

    def test_history_attachment_and_yearly_plan_survive_repeated_save(self) -> None:
        activity = self._create(title="S historií")
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
            result_note="provedeno",
        )
        source = _TMP / "protokol.pdf"
        source.write_text("protokol", encoding="utf-8")
        attachment_service.add_file(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
            str(source),
        )
        reloaded = periodic_activity_service.get_by_id(activity.id)
        assert reloaded is not None
        next_due = reloaded.next_due_date

        dialog = self._open(reloaded)
        try:
            self.assertEqual(dialog.history_table.rowCount(), 1)
            dialog.history_table.selectRow(0)
            self.assertEqual(dialog.history_attachments.entity_id, occurrence.id)
            dialog.note_edit.setPlainText("po uložení")
            self._run(dialog._editor.save_button.click)
            self.assertEqual(dialog.activity.id, activity.id)
            self.assertEqual(dialog.history_table.rowCount(), 1)
            self.assertEqual(dialog.history_attachments.entity_id, occurrence.id)
            dialog.title_edit.setText("S historií upravena")
            self._run(dialog._save_close_btn.click)
        finally:
            if dialog.isVisible():
                self._close(dialog)

        stored = periodic_activity_service.get_by_id(activity.id)
        assert stored is not None
        self.assertEqual(stored.title, "S historií upravena")
        self.assertEqual(stored.note, "po uložení")
        self.assertEqual(stored.next_due_date, next_due)
        self.assertEqual(stored.repeat_every, 1)
        self.assertEqual(stored.repeat_unit, UNIT_YEARS)
        history = periodic_activity_service.list_occurrences(activity.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].id, occurrence.id)
        self.assertEqual(history[0].result_note, "provedeno")
        files = attachment_service.get_for_entity(
            ENTITY_PERIODIC_OCCURRENCE,
            occurrence.id,
        )
        self.assertEqual([item.filename for item in files], ["protokol.pdf"])

        done = [
            row
            for row in list_periodic_rows_for_month(2026, 6, today=date(2026, 5, 1))
            if row.activity_id == activity.id
        ]
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].occurrence_id, occurrence.id)
        assert next_due is not None
        projected = [
            row
            for row in list_periodic_rows_for_month(
                next_due.year,
                next_due.month,
                today=date(2026, 5, 1),
            )
            if row.activity_id == activity.id and row.occurrence_id is None
        ]
        self.assertEqual(len(projected), 1)

    def test_list_refreshes_once_without_second_create(self) -> None:
        tab = PeriodicActivitiesTab()

        def save_and_close(dialog: PeriodicActivityDialog) -> int:
            dialog.title_edit.setText("Ze seznamu")
            dialog._save_and_close()
            return int(dialog.result())

        with (
            patch(
                "moduly.periodicke_cinnosti.ui.periodic_activities_tab.exec_maximized",
                side_effect=save_and_close,
            ),
            patch.object(
                periodic_activity_service,
                "create_activity",
                wraps=periodic_activity_service.create_activity,
            ) as create,
        ):
            tab.new_activity()
        self.assertEqual(create.call_count, 1)
        stored = [
            item
            for item in periodic_activity_service.get_all()
            if item.title == "Ze seznamu"
        ]
        self.assertEqual(len(stored), 1)
        titles = [
            tab.table.item(row, COL_TITLE).text()
            for row in range(tab.table.rowCount())
            if tab.table.item(row, COL_TITLE) is not None
        ]
        self.assertEqual(titles.count("Ze seznamu"), 1)

        def discard(dialog: PeriodicActivityDialog) -> int:
            dialog.title_edit.setText("Neukládat ze seznamu")
            with patch(_PROMPT, return_value="discard"):
                dialog._editor.close_button.click()
            return int(dialog.result())

        with (
            patch(
                "moduly.periodicke_cinnosti.ui.periodic_activities_tab.exec_maximized",
                side_effect=discard,
            ),
            patch.object(
                periodic_activity_service,
                "update_activity",
                wraps=periodic_activity_service.update_activity,
            ) as update,
        ):
            tab.open_activity(stored[0].id)
        update.assert_not_called()
        self.assertEqual(
            periodic_activity_service.get_by_id(stored[0].id).title,
            "Ze seznamu",
        )
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
