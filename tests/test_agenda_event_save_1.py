"""ÚKOL 02 – sjednocení ukládání formuláře Události."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton

_TMP = Path(tempfile.mkdtemp(prefix="agenda-event-save-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import (
        EDITOR_CLOSE_LABEL,
        EDITOR_SAVE_LABEL,
        EDITOR_UNSAVED_DISCARD_LABEL,
        confirm_unsaved_editor_close,
    )
    from moduly.schuzky.constants import DIALOG_WINDOW_TITLE, STATUS_CLOSED
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_item_task_service import (
        meeting_item_task_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_dialog import (
        MeetingDialog,
        _SAVE_CLOSE_LABEL,
        _SAVE_CONFIRMATION_TEXT,
        _UNSAVED_ABORT_LABEL,
    )
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage

_PROMPT = "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
_INFO = "moduly.schuzky.ui.meeting_dialog._exec_message_box"


class AgendaEventSave1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _future(self) -> datetime:
        AgendaEventSave1TestCase._day_offset = getattr(
            AgendaEventSave1TestCase, "_day_offset", 20
        ) + 1
        return datetime.now().replace(microsecond=0) + timedelta(
            days=AgendaEventSave1TestCase._day_offset
        )

    def _create(self, title: str = "Původní událost"):
        start = self._future()
        return meeting_service.create_meeting(
            title=title,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Zasedačka",
            agenda="Původní program",
        )

    def _open(self, meeting=None, *, template=None) -> MeetingDialog:
        dialog = MeetingDialog(meeting=meeting, template=template)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: MeetingDialog) -> None:
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

    def _labels(self, dialog: MeetingDialog) -> list[str]:
        layout = dialog.layout()
        footer = layout.itemAt(layout.count() - 1).layout()
        labels = []
        for index in range(footer.count()):
            widget = footer.itemAt(index).widget()
            if isinstance(widget, QPushButton) and widget.isVisible():
                labels.append(widget.text())
        return labels

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
            dialog.title_edit.setText("Jedna událost")
            dialog.location_edit.set_location_text("Dílna")
            dialog.agenda_items_widget.add_item()
            dialog.agenda_items_widget.title_edit.setText("Bod 1")
            dialog.agenda_items_widget.status_combo.setCurrentText("Projednáno")
            first = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0].windowTitle(), DIALOG_WINDOW_TITLE)
            self.assertEqual(first[0].text(), _SAVE_CONFIRMATION_TEXT)
            self.assertEqual(first[0].icon(), QMessageBox.Icon.Information)
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._editor.is_new)
            self.assertFalse(dialog._editor.is_dirty())
            meeting_id = int(dialog.meeting.id)
            item_id = int(dialog.agenda_items_widget.get_items()[0]["id"])
            meeting_item_task_service.create_for_item(
                meeting_id=meeting_id,
                item_id=item_id,
                title="Úkol bodu",
            )

            dialog.title_edit.setText("Jedna událost upravena")
            second = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(second), 1)
            self.assertEqual(dialog.meeting.id, meeting_id)
        finally:
            self._close(dialog)

        stored = [
            item for item in meeting_service.get_all() if item.id == meeting_id
        ]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].title, "Jedna událost upravena")
        self.assertEqual(stored[0].location, "Dílna")
        items = meeting_agenda_item_service.get_for_meeting(meeting_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, item_id)
        self.assertEqual(items[0].title, "Bod 1")
        self.assertEqual(items[0].status, "Projednáno")
        tasks = meeting_item_task_service.list_for_item(meeting_id, item_id)
        self.assertEqual([task.title for task in tasks], ["Úkol bodu"])

        reopened = self._open(meeting_service.get_by_id(meeting_id))
        try:
            self.assertEqual(reopened.title_edit.text(), "Jedna událost upravena")
            self.assertEqual(reopened.agenda_items_widget.get_items()[0]["title"], "Bod 1")
            self.assertFalse(reopened._editor.is_dirty())
        finally:
            self._close(reopened)

    def test_save_and_close_without_confirmation(self) -> None:
        meeting = self._create()
        dialog = self._open(meeting)
        dialog.agenda_edit.setPlainText("Nový program")
        dialog.status_combo.setCurrentText(STATUS_CLOSED)
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = meeting_service.get_by_id(meeting.id)
        assert stored is not None
        self.assertEqual(stored.agenda, "Nový program")
        self.assertEqual(stored.status, STATUS_CLOSED)
        dialog.deleteLater()

    def test_failed_save_keeps_window_and_draft(self) -> None:
        meeting = self._create(title="Platná")
        dialog = self._open(meeting)
        try:
            dialog.title_edit.setText("Rozepsaná")
            with (
                patch.object(
                    meeting_service,
                    "update_meeting",
                    side_effect=RuntimeError("db"),
                ),
                patch(
                    "moduly.schuzky.ui.meeting_dialog.QMessageBox.warning"
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
        stored = meeting_service.get_by_id(meeting.id)
        assert stored is not None
        self.assertEqual(stored.title, "Platná")

    def test_close_discard_and_back(self) -> None:
        meeting = self._create(title="Ponechat")
        dialog = self._open(meeting)
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
        self.assertEqual(meeting_service.get_by_id(meeting.id).title, "Ponechat")

        again = self._open(meeting_service.get_by_id(meeting.id))
        try:
            again.location_edit.set_location_text("Jiná místnost")
            with patch(_PROMPT, return_value="cancel"):
                again._editor.close_button.click()
            self.assertTrue(again.isVisible())
            self.assertEqual(again.location_edit.display_text(), "Jiná místnost")
            self.assertEqual(meeting_service.get_by_id(meeting.id).location, "Zasedačka")
        finally:
            self._close(again)

    def test_prompt_save_closes_without_confirmation(self) -> None:
        meeting = self._create()
        dialog = self._open(meeting)
        dialog.title_edit.setText("Z dotazu")
        with patch(_PROMPT, return_value="save"):
            shown = self._run(dialog._editor.close_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(meeting_service.get_by_id(meeting.id).title, "Z dotazu")
        dialog.deleteLater()

    def test_escape_and_system_close_match_close_button(self) -> None:
        meeting = self._create(title="Křížek")
        dialog = self._open(meeting)
        dialog.title_edit.setText("Z křížku ne")
        event = QCloseEvent()
        with patch(_PROMPT, return_value="discard"):
            dialog._editor.eventFilter(dialog, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(meeting_service.get_by_id(meeting.id).title, "Křížek")
        dialog.deleteLater()

        dialog = self._open(meeting_service.get_by_id(meeting.id))
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

        dialog = self._open(meeting_service.get_by_id(meeting.id))
        dialog.agenda_edit.setPlainText("Uloženo escapem")
        key = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch(_PROMPT, return_value="save"):
            shown = self._run(lambda: dialog._editor.eventFilter(dialog, key))
        self.assertEqual(shown, [])
        self.assertEqual(
            meeting_service.get_by_id(meeting.id).agenda,
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
                title=DIALOG_WINDOW_TITLE,
                abort_label=_UNSAVED_ABORT_LABEL,
            )
        self.assertEqual(decision, "cancel")
        labels = [call.args[0] for call in instance.addButton.call_args_list]
        self.assertEqual(
            labels,
            [EDITOR_SAVE_LABEL, EDITOR_UNSAVED_DISCARD_LABEL, _UNSAVED_ABORT_LABEL],
        )

    def test_template_save_creates_one_event_and_keeps_agenda(self) -> None:
        template = meeting_template_service.create_template(
            name="Ze šablony",
            event_type="Schůzka",
            location="Online",
            agenda_items=[{"title": "Úvod", "moje_sdeleni": "Text", "status": "Odloženo"}],
        )
        dialog = self._open(template=template)
        try:
            self.assertEqual(dialog.title_edit.text(), "Ze šablony")
            shown = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(shown), 1)
            self.assertIsNotNone(dialog.meeting)
            meeting_id = int(dialog.meeting.id)
            dialog.title_edit.setText("Ze šablony po úpravě")
            self._run(dialog._save_close_btn.click)
        finally:
            if dialog.isVisible():
                self._close(dialog)
        matches = [
            item
            for item in meeting_service.get_all()
            if item.id == meeting_id or (item.title or "").startswith("Ze šablony")
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].title, "Ze šablony po úpravě")
        self.assertEqual(matches[0].location, "Online")
        items = meeting_agenda_item_service.get_for_meeting(meeting_id)
        self.assertEqual(items[0].title, "Úvod")
        self.assertEqual(items[0].moje_sdeleni, "Text")

    def test_list_refreshes_once_without_second_create(self) -> None:
        page = SchuzkyPage()

        def save_and_close(dialog: MeetingDialog) -> int:
            dialog.title_edit.setText("Ze seznamu")
            dialog._save_and_close()
            return int(dialog.result())

        with (
            patch(
                "moduly.schuzky.ui.schuzky_page.exec_maximized",
                side_effect=save_and_close,
            ),
            patch.object(
                meeting_service,
                "create_meeting",
                wraps=meeting_service.create_meeting,
            ) as create,
        ):
            page.new_meeting()
        self.assertEqual(create.call_count, 1)
        stored = [
            item for item in meeting_service.get_all() if item.title == "Ze seznamu"
        ]
        self.assertEqual(len(stored), 1)

        def discard(dialog: MeetingDialog) -> int:
            dialog.title_edit.setText("Neukládat ze seznamu")
            with patch(_PROMPT, return_value="discard"):
                dialog._editor.close_button.click()
            return int(dialog.result())

        with (
            patch(
                "moduly.schuzky.ui.schuzky_page.exec_maximized",
                side_effect=discard,
            ),
            patch.object(
                meeting_service,
                "update_meeting",
                wraps=meeting_service.update_meeting,
            ) as update,
        ):
            page.open_meeting(stored[0].id)
        update.assert_not_called()
        self.assertEqual(meeting_service.get_by_id(stored[0].id).title, "Ze seznamu")
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
