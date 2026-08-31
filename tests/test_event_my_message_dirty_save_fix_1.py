"""EVENT-MY-MESSAGE-DIRTY-SAVE-FIX-1: aktivace Uložit po změně zápisků."""

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

_TMP = Path(tempfile.mkdtemp(prefix="event-my-message-dirty-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import (
        EDITOR_UNSAVED_PROMPT,
        _safe_disconnect,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import (
        AGENDA_ITEM_STATUS_DISCUSSED,
        STATUS_CANCELLED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_participant_ref import MEETING_SOURCE_PERSON
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.external_participant_dialog import ExternalParticipantDialog
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog

_EXTERNAL = {
    "full_name": "Jan Host",
    "organization": "Dodavatel s.r.o.",
    "function": "Jednatel",
    "contact": "jan@example.com",
    "note": "Host",
}


class EventMyMessageDirtySaveFix1TestCase(unittest.TestCase):
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

    def _create_meeting(self, **kwargs):
        starts = self._starts()
        defaults = {
            "title": "Událost se zápisky",
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=1),
            "status": STATUS_PLANNED,
        }
        defaults.update(kwargs)
        return meeting_service.create_meeting(**defaults)

    def _open(self, meeting) -> MeetingDialog:
        return MeetingDialog(meeting=meeting)

    def _save_enabled(self, dialog: MeetingDialog) -> bool:
        return bool(dialog._editor.save_button.isEnabled())

    def _disconnect_auto_dirty_for_notes(self, dialog: MeetingDialog) -> None:
        """Test jde přes itemsChanged → refresh_dirty, ne přes auto-tracking mark_dirty."""
        widget = dialog.agenda_items_widget
        for edit in (
            widget.moje_sdeleni_edit,
            widget.prubeh_jednani_edit,
            widget.zaver_edit,
            widget.title_edit,
        ):
            _safe_disconnect(edit.textChanged, dialog._editor.mark_dirty)
        _safe_disconnect(
            widget.status_combo.currentIndexChanged,
            dialog._editor.mark_dirty,
        )

    def _persist(self, dialog: MeetingDialog, meeting_id: int) -> None:
        meeting_service.update_meeting(meeting_id, **dialog.get_data())
        meeting_agenda_item_service.save_items(meeting_id, dialog.get_agenda_items())

    def test_open_existing_save_disabled(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        self.assertFalse(dialog._editor.is_dirty())

    def test_my_message_enables_save_via_items_changed(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": "Původní"}]
        )
        dialog = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog)
        self.assertFalse(self._save_enabled(dialog))

        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Nové sdělení")
        QApplication.processEvents()

        self.assertEqual(
            dialog.agenda_items_widget._items[0]["moje_sdeleni"],
            "Nové sdělení",
        )
        self.assertTrue(self._save_enabled(dialog))
        self.assertTrue(dialog._editor.is_dirty())

    def test_revert_message_disables_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id, [{"title": "Bod", "moje_sdeleni": "Původní"}]
        )
        dialog = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Dočasné")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))

        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Původní")
        QApplication.processEvents()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_close_with_unsaved_message_prompts(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Rozpracováno")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog._editor.request_close())
            prompt.assert_called_once()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_save_persists_and_clears_dirty(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog)
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Uložit toto")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))

        self._persist(dialog, meeting.id)
        dialog._editor.mark_clean()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

        again = self._open(meeting_service.get_by_id(meeting.id))
        self.assertEqual(
            again.agenda_items_widget.moje_sdeleni_edit.toPlainText(),
            "Uložit toto",
        )
        self.assertFalse(self._save_enabled(again))

    def test_tab_switch_does_not_enable_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(meeting.id, [{"title": "Bod"}])
        dialog = self._open(meeting)
        dialog.tabs.setCurrentIndex(1)
        QApplication.processEvents()
        dialog.tabs.setCurrentIndex(0)
        QApplication.processEvents()
        self.assertFalse(self._save_enabled(dialog))
        self.assertFalse(dialog._editor.is_dirty())

    def test_switching_item_does_not_enable_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {"title": "A", "moje_sdeleni": "sa"},
                {"title": "B", "moje_sdeleni": "sb"},
            ],
        )
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        dialog.agenda_items_widget.selectRow(1)
        QApplication.processEvents()
        self.assertEqual(dialog.agenda_items_widget.title_edit.text(), "B")
        self.assertFalse(self._save_enabled(dialog))
        self.assertFalse(dialog._editor.is_dirty())

    def test_title_status_and_other_notes_enable_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "title": "Bod",
                    "moje_sdeleni": "",
                    "prubeh_jednani": "P",
                    "zaver": "Z",
                }
            ],
        )
        dialog = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog)

        dialog.agenda_items_widget.title_edit.setText("Nový název")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))
        dialog.agenda_items_widget.title_edit.setText("Bod")
        QApplication.processEvents()
        self.assertFalse(self._save_enabled(dialog))

        dialog.agenda_items_widget.status_combo.setCurrentText(AGENDA_ITEM_STATUS_DISCUSSED)
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))

        dialog2 = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog2)
        dialog2.agenda_items_widget.prubeh_jednani_edit.setPlainText("Nový průběh")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog2))
        self.assertEqual(dialog2.agenda_items_widget._items[0]["prubeh_jednani"], "Nový průběh")

        dialog3 = self._open(meeting)
        self._disconnect_auto_dirty_for_notes(dialog3)
        dialog3.agenda_items_widget.zaver_edit.setPlainText("Nový závěr")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog3))

    def test_add_remove_reorder_enable_save(self) -> None:
        meeting = self._create_meeting()
        meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "A"}, {"title": "B"}],
        )
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))

        dialog.agenda_items_widget.add_item()
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))
        self.assertEqual(len(dialog.agenda_items_widget._items), 3)

        dialog2 = self._open(meeting)
        dialog2.agenda_items_widget.selectRow(0)
        dialog2.agenda_items_widget.remove_item()
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog2))
        self.assertEqual(len(dialog2.agenda_items_widget._items), 1)

        dialog3 = self._open(meeting)
        dialog3.agenda_items_widget.selectRow(0)
        dialog3.agenda_items_widget.move_item(1)
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog3))
        self.assertEqual(
            [item["title"] for item in dialog3.agenda_items_widget._items],
            ["B", "A"],
        )

    def test_new_event_save_stays_enabled(self) -> None:
        dialog = MeetingDialog()
        self.assertTrue(dialog._editor.is_new)
        self.assertTrue(self._save_enabled(dialog))
        dialog.agenda_items_widget.add_item()
        dialog.agenda_items_widget.moje_sdeleni_edit.setPlainText("Nová")
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))
        self.assertEqual(dialog.agenda_items_widget._items[0]["moje_sdeleni"], "Nová")

    def test_participant_change_still_enables_save(self) -> None:
        meeting = self._create_meeting()
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch.object(ExternalParticipantDialog, "get_data", return_value=dict(_EXTERNAL)):
            dialog.participants_selector.add_external()
        QApplication.processEvents()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))
        names = [
            item["full_name"]
            for item in dialog.participants_selector.external_participants()
        ]
        self.assertIn("Jan Host", names)

    def test_existing_person_still_enables_save(self) -> None:
        person = person_service.create_person(first_name="Anna", last_name="Interní")
        meeting = self._create_meeting()
        dialog = self._open(meeting)
        dialog.participants_selector.typeahead.set_ref(
            {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person.id)}
        )
        dialog.participants_selector._add_current()
        QApplication.processEvents()
        self.assertTrue(self._save_enabled(dialog))

    def test_unsaved_prompt_text_unchanged(self) -> None:
        self.assertEqual(EDITOR_UNSAVED_PROMPT, "Uložit změny před zavřením?")


if __name__ == "__main__":
    unittest.main()
