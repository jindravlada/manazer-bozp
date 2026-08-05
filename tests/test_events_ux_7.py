"""EVENTS-UX-7: externí účastníci událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import (
        ACTION_ADD_EXTERNAL_PARTICIPANT,
        ACTION_EDIT,
        ACTION_REMOVE,
        EXTERNAL_PARTICIPANT_DIALOG_TITLE,
        STATUS_CANCELLED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.external_participant_dialog import ExternalParticipantDialog
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_people_widgets import MeetingParticipantsWidget


class EventsUx7TestCase(unittest.TestCase):
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

    def test_ui_has_add_external_action(self) -> None:
        widget = MeetingParticipantsWidget()
        self.assertEqual(widget.add_external_btn.text(), ACTION_ADD_EXTERNAL_PARTICIPANT)
        self.assertEqual(widget.edit_btn.text(), ACTION_EDIT)
        self.assertEqual(widget.remove_btn.text(), ACTION_REMOVE)
        dialog = ExternalParticipantDialog()
        self.assertEqual(dialog.windowTitle(), EXTERNAL_PARTICIPANT_DIALOG_TITLE)

    def test_add_save_and_reload_external(self) -> None:
        starts = datetime.now() + timedelta(days=2)
        external = {
            "full_name": "Jan Externí",
            "organization": "Dodavatel s.r.o.",
            "function": "Jednatel",
            "contact": "jan@example.com",
            "note": "Host",
        }
        meeting = meeting_service.create_meeting(
            title="S dodavatelem",
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            status=STATUS_PLANNED,
            external_participants=[external],
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        parsed = meeting_service.parse_external_participants(reloaded)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["full_name"], "Jan Externí")
        self.assertEqual(parsed[0]["organization"], "Dodavatel s.r.o.")
        self.assertIn("Jan Externí", reloaded.participant_names)
        self.assertIn("Dodavatel s.r.o.", reloaded.participant_names)

        dialog = MeetingDialog(meeting=reloaded)
        self.assertEqual(dialog.participants_selector.external_participants(), parsed)
        self.assertEqual(
            dialog.participants_selector.list_widget.item(0).text(),
            "Jan Externí (Dodavatel s.r.o.)",
        )

    def test_edit_external(self) -> None:
        starts = datetime.now() + timedelta(days=3)
        meeting = meeting_service.create_meeting(
            title="Úprava hosta",
            starts_at=starts,
            status=STATUS_PLANNED,
            external_participants=[
                {
                    "full_name": "Petr Host",
                    "organization": "Firma A",
                    "function": "",
                    "contact": "",
                    "note": "",
                }
            ],
        )
        meeting_service.update_meeting(
            meeting.id,
            title="Úprava hosta",
            starts_at=starts,
            status=STATUS_PLANNED,
            participant_ids=[],
            external_participants=[
                {
                    "full_name": "Petr Host",
                    "organization": "Firma B",
                    "function": "Konzultant",
                    "contact": "123",
                    "note": "Aktualizováno",
                }
            ],
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        parsed = meeting_service.parse_external_participants(reloaded)
        self.assertEqual(parsed[0]["organization"], "Firma B")
        self.assertEqual(parsed[0]["function"], "Konzultant")
        self.assertEqual(parsed[0]["note"], "Aktualizováno")

        widget = MeetingParticipantsWidget()
        widget.set_participants(external_participants=parsed)
        item = widget.list_widget.item(0)
        widget.list_widget.setCurrentItem(item)

        with patch.object(
            ExternalParticipantDialog,
            "exec",
            return_value=ExternalParticipantDialog.DialogCode.Accepted,
        ), patch.object(
            ExternalParticipantDialog,
            "get_data",
            return_value={
                "full_name": "Petr Host",
                "organization": "Firma C",
                "function": "Konzultant",
                "contact": "123",
                "note": "UI",
            },
        ):
            widget.edit_selected()
        self.assertEqual(
            widget.external_participants()[0]["organization"],
            "Firma C",
        )

    def test_remove_external(self) -> None:
        widget = MeetingParticipantsWidget()
        widget.set_participants(
            external_participants=[
                {
                    "full_name": "Dočasný",
                    "organization": "",
                    "function": "",
                    "contact": "",
                    "note": "",
                }
            ]
        )
        self.assertEqual(len(widget.external_participants()), 1)
        widget.list_widget.setCurrentRow(0)
        widget.remove_selected()
        self.assertEqual(widget.external_participants(), [])

    def test_mix_internal_and_external(self) -> None:
        person = person_service.create_person(first_name="Anna", last_name="Interní")
        starts = datetime.now() + timedelta(days=4)
        meeting = meeting_service.create_meeting(
            title="Smíšená schůzka",
            starts_at=starts,
            status=STATUS_PLANNED,
            participant_ids=[person.id],
            external_participants=[
                {
                    "full_name": "Karel Externí",
                    "organization": "Partner a.s.",
                    "function": "BOZP",
                    "contact": "",
                    "note": "",
                }
            ],
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(meeting_service.parse_participant_ids(reloaded), [person.id])
        externals = meeting_service.parse_external_participants(reloaded)
        self.assertEqual(len(externals), 1)
        self.assertIn("Interní", reloaded.participant_names)
        self.assertIn("Karel Externí", reloaded.participant_names)

        dialog = MeetingDialog(meeting=reloaded)
        self.assertEqual(dialog.participants_selector.selected_person_ids(), [person.id])
        self.assertEqual(
            dialog.participants_selector.external_participants()[0]["full_name"],
            "Karel Externí",
        )
        self.assertEqual(dialog.participants_selector.list_widget.count(), 2)

        # Externí osoba není v číselníku Osoby
        names = {p.display_name for p in person_service.get_all(include_inactive=True)}
        self.assertNotIn("Karel Externí", names)

    def test_external_name_required(self) -> None:
        dialog = ExternalParticipantDialog()
        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_accept()
            warning.assert_called_once()
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)


if __name__ == "__main__":
    unittest.main()
