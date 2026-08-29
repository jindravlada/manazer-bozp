"""EVENT-PARTICIPANT-DIRTY-SAVE-1: dirty stav po změně osob v editoru události."""

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

_TMP = Path(tempfile.mkdtemp(prefix="event-participant-dirty-1-"))

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
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
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


class EventParticipantDirtySave1TestCase(unittest.TestCase):
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

    def _planned_meeting(self, **kwargs):
        starts = datetime.now() + timedelta(days=3)
        defaults = {
            "title": "Plánovaná událost",
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

    def _add_external(self, dialog: MeetingDialog, data: dict | None = None) -> None:
        payload = dict(data or _EXTERNAL)
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch.object(ExternalParticipantDialog, "get_data", return_value=payload):
            dialog.participants_selector.add_external()

    def _add_existing_person(self, dialog: MeetingDialog, person_id: int) -> None:
        dialog.participants_selector.typeahead.set_ref(
            {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person_id)}
        )
        dialog.participants_selector._add_current()

    def test_open_existing_save_disabled(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_add_other_person_enables_save(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        self._add_external(dialog)
        names = [item["full_name"] for item in dialog.participants_selector.external_participants()]
        self.assertIn("Jan Host", names)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_add_existing_person_enables_save(self) -> None:
        person = person_service.create_person(first_name="Anna", last_name="Interní")
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_existing_person(dialog, person.id)
        self.assertIn(person.id, dialog.participants_selector.selected_person_ids())
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_cancel_add_keeps_clean(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Rejected,
        ):
            dialog.participants_selector.add_external()
        self.assertEqual(dialog.participants_selector.external_participants(), [])
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_real_edit_enables_save(self) -> None:
        meeting = self._planned_meeting(external_participants=[_EXTERNAL])
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        dialog.participants_selector.list_widget.setCurrentRow(0)
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch.object(
            ExternalParticipantDialog,
            "get_data",
            return_value={**_EXTERNAL, "organization": "Nová firma"},
        ):
            dialog.participants_selector.edit_selected()
        self.assertEqual(
            dialog.participants_selector.external_participants()[0]["organization"],
            "Nová firma",
        )
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_cancel_edit_keeps_clean(self) -> None:
        meeting = self._planned_meeting(external_participants=[_EXTERNAL])
        dialog = self._open(meeting)
        dialog.participants_selector.list_widget.setCurrentRow(0)
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Rejected,
        ):
            dialog.participants_selector.edit_selected()
        self.assertEqual(
            dialog.participants_selector.external_participants()[0]["organization"],
            "Dodavatel s.r.o.",
        )
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_confirm_edit_without_change_stays_clean(self) -> None:
        meeting = self._planned_meeting(external_participants=[_EXTERNAL])
        dialog = self._open(meeting)
        dialog.participants_selector.list_widget.setCurrentRow(0)
        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=QDialog.DialogCode.Accepted,
        ), patch.object(ExternalParticipantDialog, "get_data", return_value=dict(_EXTERNAL)):
            dialog.participants_selector.edit_selected()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_remove_enables_save(self) -> None:
        meeting = self._planned_meeting(external_participants=[_EXTERNAL])
        dialog = self._open(meeting)
        dialog.participants_selector.list_widget.setCurrentRow(0)
        dialog.participants_selector.remove_selected()
        self.assertEqual(dialog.participants_selector.external_participants(), [])
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_remove_without_selection_keeps_clean(self) -> None:
        meeting = self._planned_meeting(external_participants=[_EXTERNAL])
        dialog = self._open(meeting)
        dialog.participants_selector.list_widget.clearSelection()
        dialog.participants_selector.remove_selected()
        self.assertEqual(len(dialog.participants_selector.external_participants()), 1)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_save_persists_and_clears_dirty(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_external(dialog)
        self.assertTrue(self._save_enabled(dialog))
        meeting_service.update_meeting(meeting.id, **dialog.get_data())
        dialog._editor.mark_clean()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

        reloaded = meeting_service.get_by_id(meeting.id)
        parsed = meeting_service.parse_external_participants(reloaded)
        self.assertEqual(parsed[0]["full_name"], "Jan Host")
        again = self._open(reloaded)
        self.assertEqual(again.participants_selector.external_participants()[0]["full_name"], "Jan Host")
        self.assertFalse(again._editor.is_dirty())
        self.assertFalse(self._save_enabled(again))

    def test_close_with_unsaved_change_prompts(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_external(dialog)
        self.assertTrue(self._save_enabled(dialog))
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ) as prompt:
            self.assertFalse(dialog._editor.request_close())
            prompt.assert_called_once()
            self.assertEqual(prompt.call_args.kwargs.get("title"), dialog.windowTitle())
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_close_clean_skips_prompt(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self.assertFalse(self._save_enabled(dialog))
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
        ) as prompt:
            self.assertTrue(dialog._editor.request_close())
            prompt.assert_not_called()

    def test_discard_drops_participant_change(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_external(dialog)
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        reloaded = meeting_service.get_by_id(meeting.id)
        self.assertEqual(meeting_service.parse_external_participants(reloaded), [])

    def test_close_cancel_keeps_dialog_dirty(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_external(dialog)
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ):
            self.assertFalse(dialog._editor.request_close())
        self.assertTrue(dialog.isVisible() or dialog.result() == 0)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))
        self.assertEqual(
            dialog.participants_selector.external_participants()[0]["full_name"],
            "Jan Host",
        )

    def test_failed_save_keeps_dirty(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        self._add_external(dialog)
        with patch.object(dialog, "_validate", return_value=False):
            dialog._editor.save_button.click()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save_enabled(dialog))

    def test_refresh_dirty_does_not_force_dirty_when_unchanged(self) -> None:
        meeting = self._planned_meeting()
        dialog = self._open(meeting)
        dialog._editor.refresh_dirty()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(self._save_enabled(dialog))

    def test_unsaved_prompt_text_unchanged(self) -> None:
        self.assertEqual(EDITOR_UNSAVED_PROMPT, "Uložit změny před zavřením?")


if __name__ == "__main__":
    unittest.main()
