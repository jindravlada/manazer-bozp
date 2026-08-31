"""EVENT-MY-MESSAGE-PERSISTENCE-1: uložení pole Moje sdělení v editoru Události."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="event-my-message-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EDITOR_UNSAVED_PROMPT
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_participant_ref import MEETING_SOURCE_PERSON
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog

_MULTILINE = (
    "První odstavec s háčky: příliš žluťoučký kůň\n"
    "\n"
    "Druhý odstavec – delší víceřádkový text."
)


class EventMyMessagePersistence1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") == STATUS_CANCELLED:
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                event_type=getattr(meeting, "event_type", None) or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                external_participants=[],
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
                priority=getattr(meeting, "priority", None) or "Normální",
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )

    def _starts(self) -> datetime:
        return datetime.now() + timedelta(days=3)

    def _create_meeting(self, *, status: str = STATUS_PLANNED, **kwargs):
        starts = self._starts()
        defaults = {
            "title": "Událost se zápisky",
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=1),
            "status": status,
        }
        defaults.update(kwargs)
        return meeting_service.create_meeting(**defaults)

    def _persist(self, dialog: MeetingDialog, meeting_id: int | None = None) -> int:
        data = dialog.get_data()
        if meeting_id is None:
            meeting = meeting_service.create_meeting(**data)
            meeting_id = int(meeting.id)
        else:
            meeting_service.update_meeting(meeting_id, **data)
        meeting_agenda_item_service.save_items(meeting_id, dialog.get_agenda_items())
        return meeting_id

    def _open(self, meeting) -> MeetingDialog:
        return MeetingDialog(meeting=meeting)

    def _set_dates(self, dialog: MeetingDialog) -> None:
        starts = self._starts()
        dialog.starts_at_edit.set_datetime(starts)
        dialog.ends_at_edit.set_datetime(starts + timedelta(hours=1))

    def _working_copy_message(self, dialog: MeetingDialog) -> str:
        items = dialog.agenda_items_widget._items
        self.assertTrue(items)
        return items[0].get("moje_sdeleni") or ""

    def _reopen_message(self, meeting_id: int) -> str:
        meeting = meeting_service.get_by_id(meeting_id)
        assert meeting is not None
        dialog = self._open(meeting)
        return dialog.agenda_items_widget.moje_sdeleni_edit.toPlainText()

    def test_existing_event_save_reload_keeps_message(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "Bod", "moje_sdeleni": "", "prubeh_jednani": "P", "zaver": "Z"}],
        )
        dialog = self._open(meeting)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Uložené sdělení")
        self.assertEqual(self._working_copy_message(dialog), "Uložené sdělení")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())

        with patch.object(dialog, "_validate", return_value=True):
            dialog._editor.save_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self._persist(dialog, meeting.id)

        self.assertEqual(self._reopen_message(meeting.id), "Uložené sdělení")
        loaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(loaded[0].prubeh_jednani, "P")
        self.assertEqual(loaded[0].zaver, "Z")

    def test_new_event_with_message_save_reload(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Nová se sdělením")
        self._set_dates(dialog)
        dialog.agenda_items_widget.add_item()
        dialog.agenda_items_widget.title_edit.setText("Téma")
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Sdělení nové")
        self.assertEqual(self._working_copy_message(dialog), "Sdělení nové")

        with patch.object(dialog, "_validate", return_value=True):
            dialog._editor.save_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        meeting_id = self._persist(dialog)

        self.assertEqual(self._reopen_message(meeting_id), "Sdělení nové")
        loaded = meeting_agenda_item_service.get_for_meeting(meeting_id)
        self.assertEqual(loaded[0].title, "Téma")

    def test_multiline_diacritics_preserved(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText(_MULTILINE)
        self.assertEqual(self._working_copy_message(dialog), _MULTILINE)
        self._persist(dialog, meeting.id)
        self.assertEqual(self._reopen_message(meeting.id), _MULTILINE)

    def test_change_saved_message(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": "Původní"}]
        )
        dialog = self._open(meeting)
        self.assertEqual(dialog.agenda_items_widget.moje_sdeleni_edit.toPlainText(), "Původní")
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Upravené")
        self._persist(dialog, meeting.id)
        self.assertEqual(self._reopen_message(meeting.id), "Upravené")

    def test_clear_saved_message_persists_empty(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": "Ke smazání"}]
        )
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("")
        self.assertEqual(self._working_copy_message(dialog), "")
        self.assertTrue(dialog._editor.is_dirty())
        self._persist(dialog, meeting.id)
        self.assertEqual(self._reopen_message(meeting.id), "")
        loaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(loaded[0].moje_sdeleni, "")

    def test_discard_does_not_save_message(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": "Původní"}]
        )
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Nemá se uložit")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        self.assertEqual(
            meeting_agenda_item_service.get_for_meeting(meeting.id)[0].moje_sdeleni,
            "Původní",
        )
        self.assertEqual(self._reopen_message(meeting.id), "Původní")

    def test_unsaved_change_enables_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        from core.widgets.editor_dialog_controller import _safe_disconnect

        _safe_disconnect(
            dialog.agenda_items_widget.moje_sdeleni_edit.textChanged,
            dialog._editor.mark_dirty,
        )
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Změna")
        QApplication.processEvents()
        self.assertTrue(dialog._editor.save_button.isEnabled())
        self.assertTrue(dialog._editor.is_dirty())

    def test_successful_save_marks_dialog_clean(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Po uložení")
        self.assertTrue(dialog._editor.is_dirty())
        self._persist(dialog, meeting.id)
        dialog._editor.mark_clean()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

    def test_close_with_unsaved_message_prompts(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Rozpracováno")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog._editor.request_close())
            prompt.assert_called_once()
            self.assertEqual(prompt.call_args.kwargs.get("title"), dialog.windowTitle())
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())

    def test_message_change_does_not_wipe_notes_or_people(self) -> None:
        person = person_service.create_person(first_name="Anna", last_name="Účastnice")
        meeting = self._create_meeting(
            participant_refs=[
                {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person.id)}
            ],
        )
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Bezpečnost",
                    "moje_sdeleni": "Staré sdělení",
                    "prubeh_jednani": "Diskuze o OOPP",
                    "zaver": "Doplnit registr",
                }
            ],
        )
        dialog = self._open(meeting)
        self.assertEqual(dialog.participants_selector.selected_person_ids(), [person.id])
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Nové sdělení")
        self._persist(dialog, meeting.id)

        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(meeting_service.parse_participant_ids(reloaded), [person.id])
        items = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Bezpečnost")
        self.assertEqual(items[0].moje_sdeleni, "Nové sdělení")
        self.assertEqual(items[0].prubeh_jednani, "Diskuze o OOPP")
        self.assertEqual(items[0].zaver, "Doplnit registr")

    def test_closed_event_same_dialog_persists_message(self) -> None:
        meeting = self._create_meeting(status=STATUS_CLOSED, title="Uskutečněná")
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Zápis po akci")
        self._persist(dialog, meeting.id)
        self.assertEqual(self._reopen_message(meeting.id), "Zápis po akci")

    def test_null_message_opens_without_error(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting_service.get_by_id(meeting.id))
        self.assertEqual(dialog.agenda_items_widget.moje_sdeleni_edit.toPlainText(), "")
        self.assertFalse(dialog._editor.is_dirty())

        payload = meeting_agenda_item_service.item_to_dict(
            type(
                "Obj",
                (),
                {
                    "id": 1,
                    "meeting_id": 1,
                    "display_order": 10,
                    "title": "Bod",
                    "status": None,
                    "moje_sdeleni": None,
                    "prubeh_jednani": None,
                    "zaver": None,
                },
            )()
        )
        self.assertEqual(payload["moje_sdeleni"], "")

    def test_tab_switch_does_not_write(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": ""}]
        )
        dialog = self._open(meeting)
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        self.assertFalse(dialog._editor.is_dirty())
        loaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(loaded[0].moje_sdeleni, "")

    def test_unsaved_prompt_text_unchanged(self) -> None:
        self.assertEqual(EDITOR_UNSAVED_PROMPT, "Uložit změny před zavřením?")


if __name__ == "__main__":
    unittest.main()
