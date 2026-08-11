"""AGENDA-EVENT-REMINDER-1: remind_from pro Události a panel Připomínky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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

    from core.dashboard.attention_item import ITEM_TYPE_MEETING
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import (
        classify_reminder_meetings,
        meeting_should_appear_in_reminders,
    )
    from moduly.schuzky.constants import (
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import (
        MeetingValidationError,
        meeting_service,
    )
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class AgendaEventReminder1TestCase(unittest.TestCase):
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
                remind_from=getattr(meeting, "remind_from", None),
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
                priority=getattr(meeting, "priority", None) or "Normální",
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )

    def _dt(self, day: date, hour: int = 10) -> datetime:
        return datetime(day.year, day.month, day.day, hour, 0, 0)

    def _ids(self, groups) -> set[int]:
        burning, due_today = groups
        return {m.id for m in burning} | {m.id for m in due_today}

    def test_a_future_event_without_remind_not_shown(self) -> None:
        today = date(2026, 9, 1)
        meeting = meeting_service.create_meeting(
            title="A budoucí",
            starts_at=self._dt(today + timedelta(days=30)),
            remind_from=None,
            status=STATUS_PLANNED,
        )
        self.assertFalse(meeting_should_appear_in_reminders(meeting, today))
        self.assertNotIn(meeting.id, self._ids(classify_reminder_meetings([meeting], today)))

    def test_b_remind_from_today_shown(self) -> None:
        today = date(2026, 9, 1)
        meeting = meeting_service.create_meeting(
            title="B připomenout dnes",
            starts_at=self._dt(today + timedelta(days=30)),
            remind_from=today,
            status=STATUS_PLANNED,
        )
        self.assertTrue(meeting_should_appear_in_reminders(meeting, today))
        self.assertIn(meeting.id, self._ids(classify_reminder_meetings([meeting], today)))

    def test_c_appears_when_remind_from_reached(self) -> None:
        remind = date(2026, 9, 15)
        event_day = date(2026, 9, 30)
        meeting = meeting_service.create_meeting(
            title="C od data",
            starts_at=self._dt(event_day),
            remind_from=remind,
            status=STATUS_PLANNED,
        )
        self.assertFalse(meeting_should_appear_in_reminders(meeting, date(2026, 9, 14)))
        self.assertTrue(meeting_should_appear_in_reminders(meeting, remind))

    def test_d_event_day_without_remind(self) -> None:
        today = date(2026, 9, 30)
        meeting = meeting_service.create_meeting(
            title="D den události",
            starts_at=self._dt(today),
            remind_from=None,
            status=STATUS_PLANNED,
        )
        self.assertTrue(meeting_should_appear_in_reminders(meeting, today))

    def test_e_planned_after_date_stays(self) -> None:
        event_day = date(2026, 9, 30)
        meeting = meeting_service.create_meeting(
            title="E po datu",
            starts_at=self._dt(event_day),
            remind_from=None,
            status=STATUS_PLANNED,
        )
        self.assertTrue(meeting_should_appear_in_reminders(meeting, date(2026, 10, 5)))
        burning, due = classify_reminder_meetings([meeting], date(2026, 10, 5))
        self.assertEqual([m.id for m in burning], [meeting.id])
        self.assertEqual(due, [])

    def test_f_closed_hidden(self) -> None:
        today = date(2026, 9, 1)
        meeting = meeting_service.create_meeting(
            title="F uzavřeno",
            starts_at=self._dt(date(2026, 8, 1)),
            status=STATUS_CLOSED,
        )
        self.assertFalse(meeting_should_appear_in_reminders(meeting, today))

    def test_g_cancelled_hidden(self) -> None:
        today = date(2026, 9, 1)
        meeting = meeting_service.create_meeting(
            title="G zrušeno",
            starts_at=self._dt(date(2026, 8, 1)),
            status=STATUS_CANCELLED,
        )
        self.assertFalse(meeting_should_appear_in_reminders(meeting, today))

    def test_h_remind_after_event_rejected(self) -> None:
        with self.assertRaises(MeetingValidationError):
            meeting_service.create_meeting(
                title="H neplatné",
                starts_at=self._dt(date(2026, 9, 1)),
                remind_from=date(2026, 9, 2),
            )
        self.assertIsNotNone(
            meeting_service.validate_remind_from(
                date(2026, 9, 2),
                self._dt(date(2026, 9, 1)),
            )
        )

    def test_i_remind_can_be_cleared(self) -> None:
        meeting = meeting_service.create_meeting(
            title="I clear",
            starts_at=self._dt(date(2026, 10, 1)),
            remind_from=date(2026, 9, 1),
        )
        updated = meeting_service.update_meeting(
            meeting.id,
            title=meeting.title,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            remind_from=None,
            status=meeting.status,
            priority=meeting.priority,
            event_type=meeting.event_type,
            location=meeting.location or "",
            organizer_person_id=meeting.organizer_person_id,
            participant_ids=meeting_service.parse_participant_ids(meeting),
            external_participants=meeting_service.parse_external_participants(meeting),
            agenda=meeting.agenda or "",
        )
        self.assertIsNone(updated.remind_from)

    def test_j_template_creates_null_remind(self) -> None:
        template = meeting_template_service.create_template(
            name="Šablona reminder",
            event_type="Schůzka",
            location="Místnost",
        )
        data = meeting_template_service.meeting_data_from_template(template)
        data["title"] = "Ze šablony"
        data["starts_at"] = self._dt(date(2026, 11, 1))
        data.setdefault("remind_from", None)
        meeting = meeting_service.create_meeting(**data)
        self.assertIsNone(meeting.remind_from)
        self.assertFalse(
            meeting_should_appear_in_reminders(meeting, date(2026, 9, 1))
        )
        self.assertTrue(
            meeting_should_appear_in_reminders(meeting, date(2026, 11, 1))
        )

        dialog = MeetingDialog(template=template)
        self.assertIsNone(dialog.get_data().get("remind_from"))
        tip = dialog.remind_from_edit.toolTip()
        self.assertIn("Pracovní ploše", tip)
        self.assertIn("Připomínky", tip)
        dialog._editor.force_close()

    def test_k_upcoming_unchanged_for_future_without_remind(self) -> None:
        today = date(2026, 9, 1)
        meeting = meeting_service.create_meeting(
            title="K nadcházející",
            starts_at=self._dt(today + timedelta(days=20)),
            remind_from=None,
            status=STATUS_PLANNED,
        )
        self.assertFalse(meeting_should_appear_in_reminders(meeting, today))
        upcoming = get_attention_items(today=today)
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id
                for item in upcoming
            )
        )

    def test_dialog_rejects_invalid_remind(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Neplatný remind")
        dialog.starts_at_edit.set_datetime(self._dt(date(2026, 9, 1)))
        dialog.remind_from_edit.set_date_value(date(2026, 9, 15))
        with patch("moduly.schuzky.ui.meeting_dialog.QMessageBox.warning") as warn:
            self.assertFalse(dialog._validate())
            warn.assert_called_once()
        dialog._editor.force_close()


if __name__ == "__main__":
    unittest.main()
