"""EVENTS-LOGIC-1: zákaz minulého termínu a kontrola časových konfliktů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
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

    from moduly.schuzky.constants import (
        CONFLICT_BTN_EDIT,
        CONFLICT_BTN_SAVE,
        CONFLICT_DIALOG_TITLE,
        PAST_PLANNED_BACK_BUTTON,
        PAST_PLANNED_START_MESSAGE,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_HELD,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_conflict_dialog import (
        CONFLICT_CHOICE_CANCEL,
        CONFLICT_CHOICE_EDIT,
        CONFLICT_CHOICE_SAVE,
        MeetingConflictDialog,
    )
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class EventsLogic1TestCase(unittest.TestCase):
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
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
                priority=getattr(meeting, "priority", None) or "Normální",
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )

    def test_new_planned_cannot_save_in_past(self) -> None:
        past = datetime.now() - timedelta(hours=2)
        self.assertTrue(
            meeting_service.is_planned_start_in_past_forbidden(
                status=STATUS_PLANNED,
                starts_at=past,
                existing=None,
            )
        )
        shown: list[str] = []

        def _fake_show(self_dialog):
            shown.append(PAST_PLANNED_START_MESSAGE)

        dialog = MeetingDialog()
        dialog.starts_at_edit.set_datetime(past)
        dialog.ends_at_edit.set_datetime(past + timedelta(hours=1))
        dialog.status_combo.setCurrentText(STATUS_PLANNED)
        with patch.object(MeetingDialog, "_show_past_start_blocked", _fake_show):
            dialog._on_accept()
        self.assertEqual(shown, [PAST_PLANNED_START_MESSAGE])
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)
        self.assertEqual(PAST_PLANNED_BACK_BUTTON, "Zpět k úpravě")

    def test_future_planned_can_save(self) -> None:
        future = datetime.now() + timedelta(days=2)
        self.assertFalse(
            meeting_service.is_planned_start_in_past_forbidden(
                status=STATUS_PLANNED,
                starts_at=future,
                existing=None,
            )
        )
        dialog = MeetingDialog()
        dialog.title_edit.setText("Budoucí")
        dialog.starts_at_edit.set_datetime(future)
        dialog.ends_at_edit.set_datetime(future + timedelta(hours=1))
        dialog._on_accept()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_existing_past_planned_can_change_to_held(self) -> None:
        past = datetime.now() - timedelta(days=3)
        meeting = meeting_service.create_meeting(
            title="Stará",
            starts_at=past,
            ends_at=past + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        # Stále Naplánováno se stejným časem – neblokovat.
        self.assertFalse(
            meeting_service.is_planned_start_in_past_forbidden(
                status=STATUS_PLANNED,
                starts_at=past,
                existing=meeting,
            )
        )
        dialog = MeetingDialog(meeting=meeting)
        dialog.status_combo.setCurrentText(STATUS_HELD)
        dialog._on_accept()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

        meeting_service.update_meeting(
            meeting.id,
            title=meeting.title,
            event_type=meeting.event_type,
            starts_at=past,
            ends_at=past + timedelta(hours=1),
            status=STATUS_HELD,
        )
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, STATUS_HELD)

    def test_existing_cannot_set_new_past_term_as_planned(self) -> None:
        past = datetime.now() - timedelta(days=3)
        older = past - timedelta(days=1)
        meeting = meeting_service.create_meeting(
            title="Existující",
            starts_at=past,
            ends_at=past + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        self.assertTrue(
            meeting_service.is_planned_start_in_past_forbidden(
                status=STATUS_PLANNED,
                starts_at=older,
                existing=meeting,
            )
        )

    def test_overlap_finds_conflict(self) -> None:
        start = datetime.now() + timedelta(days=5)
        a = meeting_service.create_meeting(
            title="A",
            event_type="Schůzka",
            starts_at=start,
            ends_at=start + timedelta(hours=2),
            location="Sál",
            status=STATUS_PLANNED,
        )
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=3),
        )
        self.assertEqual([c.id for c in conflicts], [a.id])
        line = meeting_service.format_conflict_line(a)
        self.assertIn("A", line)
        self.assertIn("Sál", line)
        self.assertIn("Schůzka", line)

    def test_adjacent_intervals_not_conflict(self) -> None:
        start = datetime.now() + timedelta(days=6)
        meeting_service.create_meeting(
            title="Ráno",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=2),
        )
        self.assertEqual(conflicts, [])

    def test_exclude_self(self) -> None:
        start = datetime.now() + timedelta(days=7)
        meeting = meeting_service.create_meeting(
            title="Já",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            exclude_id=meeting.id,
        )
        self.assertEqual(conflicts, [])

    def test_ignore_non_planned_statuses(self) -> None:
        start = datetime.now() + timedelta(days=8)
        for status, title in (
            (STATUS_HELD, "Proběhlo"),
            (STATUS_CLOSED, "Uzavřeno"),
            (STATUS_CANCELLED, "Zrušeno"),
        ):
            meeting_service.create_meeting(
                title=title,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                status=status,
            )
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        self.assertEqual(conflicts, [])

    def test_missing_end_uses_one_hour(self) -> None:
        start = datetime.now() + timedelta(days=9)
        meeting_service.create_meeting(
            title="Bez konce",
            starts_at=start,
            ends_at=None,
            status=STATUS_PLANNED,
        )
        # Překryv v rámci +1 h
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start + timedelta(minutes=30),
            ends_at=start + timedelta(hours=2),
        )
        self.assertEqual(len(conflicts), 1)
        # Navazující na efektivní konec (start+1h) není konflikt
        conflicts_adj = meeting_service.find_planned_conflicts(
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=2),
        )
        self.assertEqual(conflicts_adj, [])
        # Uložená data beze změny
        stored = meeting_service.get_all()
        bare = next(m for m in stored if m.title == "Bez konce")
        self.assertIsNone(bare.ends_at)

    def test_multiday_overlap(self) -> None:
        start = datetime.now() + timedelta(days=10)
        meeting_service.create_meeting(
            title="Vícedenní",
            starts_at=start,
            ends_at=start + timedelta(days=2),
            status=STATUS_PLANNED,
        )
        conflicts = meeting_service.find_planned_conflicts(
            starts_at=start + timedelta(days=1, hours=3),
            ends_at=start + timedelta(days=1, hours=4),
        )
        self.assertEqual(len(conflicts), 1)

    def test_conflict_dialog_edit_does_not_accept(self) -> None:
        start = datetime.now() + timedelta(days=11)
        meeting_service.create_meeting(
            title="Blok",
            starts_at=start,
            ends_at=start + timedelta(hours=2),
            status=STATUS_PLANNED,
        )
        dialog = MeetingDialog()
        dialog.title_edit.setText("Nová")
        dialog.starts_at_edit.set_datetime(start + timedelta(hours=1))
        dialog.ends_at_edit.set_datetime(start + timedelta(hours=3))

        with patch.object(
            MeetingConflictDialog,
            "exec",
            return_value=CONFLICT_CHOICE_EDIT,
        ):
            dialog._on_accept()
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)
        self.assertEqual(dialog.title_edit.text(), "Nová")

    def test_conflict_dialog_save_anyway_accepts(self) -> None:
        start = datetime.now() + timedelta(days=12)
        meeting_service.create_meeting(
            title="Blok 2",
            starts_at=start,
            ends_at=start + timedelta(hours=2),
            status=STATUS_PLANNED,
        )
        dialog = MeetingDialog()
        dialog.title_edit.setText("Přesto")
        dialog.starts_at_edit.set_datetime(start + timedelta(hours=1))
        dialog.ends_at_edit.set_datetime(start + timedelta(hours=3))

        with patch.object(
            MeetingConflictDialog,
            "exec",
            return_value=CONFLICT_CHOICE_SAVE,
        ):
            dialog._on_accept()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_conflict_dialog_cancel_keeps_editor_data(self) -> None:
        start = datetime.now() + timedelta(days=13)
        meeting_service.create_meeting(
            title="Blok 3",
            starts_at=start,
            ends_at=start + timedelta(hours=2),
            status=STATUS_PLANNED,
        )
        dialog = MeetingDialog()
        dialog.title_edit.setText("Rozepsáno")
        dialog.location_edit.set_location_text("Místnost X")
        dialog.starts_at_edit.set_datetime(start + timedelta(hours=1))
        dialog.ends_at_edit.set_datetime(start + timedelta(hours=3))

        with patch.object(
            MeetingConflictDialog,
            "exec",
            return_value=CONFLICT_CHOICE_CANCEL,
        ):
            dialog._on_accept()
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)
        self.assertEqual(dialog.title_edit.text(), "Rozepsáno")
        self.assertEqual(dialog.location_edit.display_text(), "Místnost X")

    def test_conflict_rechecked_after_time_change(self) -> None:
        start = datetime.now() + timedelta(days=14)
        meeting_service.create_meeting(
            title="Původní",
            starts_at=start,
            ends_at=start + timedelta(hours=2),
            status=STATUS_PLANNED,
        )
        dialog = MeetingDialog()
        dialog.starts_at_edit.set_datetime(start + timedelta(hours=1))
        dialog.ends_at_edit.set_datetime(start + timedelta(hours=3))

        calls: list[int] = []

        def _exec(self_dialog):
            calls.append(1)
            return CONFLICT_CHOICE_EDIT

        with patch.object(MeetingConflictDialog, "exec", _exec):
            dialog._on_accept()
            self.assertEqual(len(calls), 1)
            # Po úpravě času mimo konflikt – další uložení bez dialogu
            free = start + timedelta(hours=5)
            dialog.starts_at_edit.set_datetime(free)
            dialog.ends_at_edit.set_datetime(free + timedelta(hours=1))
            dialog._on_accept()
            self.assertEqual(len(calls), 1)
            self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_conflict_dialog_ui_labels(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        start = datetime.now() + timedelta(days=15)
        meeting = meeting_service.create_meeting(
            title="Konfliktní",
            event_type="Porada",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Aula",
            status=STATUS_PLANNED,
        )
        dlg = MeetingConflictDialog([meeting])
        self.assertEqual(dlg.windowTitle(), CONFLICT_DIALOG_TITLE)
        buttons = [b.text() for b in dlg.findChildren(QPushButton)]
        self.assertIn(CONFLICT_BTN_EDIT, buttons)
        self.assertIn(CONFLICT_BTN_SAVE, buttons)
        self.assertIn("Zrušit", buttons)
        labels = " ".join(label.text() for label in dlg.findChildren(QLabel))
        self.assertIn("Konfliktní", labels)
        self.assertIn("Aula", labels)
        self.assertIn("Porada", labels)


if __name__ == "__main__":
    unittest.main()
