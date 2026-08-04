"""MEETINGS-UX-3: ergonomie termínu a výběru osob."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

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

    from core.widgets.dialog_utils import prepare_work_dialog_maximized
    from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.schuzky.sluzby.meeting_person_link import (
        ensure_person_for_thp_worker,
        find_person_matching_thp,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_people_widgets import (
        MeetingOrganizerWidget,
        MeetingParticipantsWidget,
        _MultiPersonPickDialog,
        _MultiThpPickDialog,
        _SinglePersonPickDialog,
    )


class MeetingsUx3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_editor_opens_maximized(self) -> None:
        dialog = MeetingDialog()
        prepare_work_dialog_maximized(dialog)
        self.assertTrue(bool(dialog.windowState() & Qt.WindowState.WindowMaximized))
        self.assertFalse(bool(dialog.windowState() & Qt.WindowState.WindowFullScreen))
        dialog.close()

        from moduly.schuzky import ui as schuzky_ui

        page_file = Path(schuzky_ui.__file__).parent / "schuzky_page.py"
        text = page_file.read_text(encoding="utf-8")
        self.assertIn("exec_maximized", text)
        self.assertGreaterEqual(text.count("exec_maximized"), 2)

    def test_start_and_end_manual_edit(self) -> None:
        widget = NullableDateTimeEdit()
        starts = datetime(2026, 8, 12, 9, 0, 0)
        widget.set_datetime(starts)
        self.assertTrue(widget.edit.isEnabled())
        self.assertEqual(widget.get_datetime(), starts)

        widget.edit.setDateTime(widget.edit.dateTime().addSecs(30 * 60))
        self.assertEqual(widget.get_datetime(), datetime(2026, 8, 12, 9, 30, 0))

        ends = NullableDateTimeEdit()
        ends.set_datetime(datetime(2026, 8, 12, 10, 0, 0))
        ends.edit.setDateTime(ends.edit.dateTime().addDays(1))
        self.assertEqual(ends.get_datetime().date().isoformat(), "2026-08-13")
        self.assertEqual(ends.get_datetime().hour, 10)

    def test_calendar_does_not_insert_now_without_selection(self) -> None:
        widget = NullableDateTimeEdit()
        self.assertFalse(widget.has_value())
        with patch.object(QDialog, "exec", return_value=0):
            widget.open_calendar()
        self.assertFalse(widget.has_value())
        self.assertIsNone(widget.get_datetime())

        preserved = datetime(2026, 8, 12, 14, 25, 0)
        widget.set_datetime(preserved)
        with patch.object(QDialog, "exec", return_value=0):
            widget.open_calendar()
        self.assertEqual(widget.get_datetime(), preserved)

    def test_calendar_keeps_manual_time_when_date_selected(self) -> None:
        widget = NullableDateTimeEdit()
        widget.set_datetime(datetime(2026, 8, 12, 14, 25, 0))

        def _pick_other_day(self_widget: NullableDateTimeEdit) -> None:
            current = self_widget.get_datetime()
            assert current is not None
            keep_time = current.time()
            self_widget.set_datetime(
                datetime(2026, 8, 20, keep_time.hour, keep_time.minute, keep_time.second)
            )

        with patch.object(NullableDateTimeEdit, "open_calendar", _pick_other_day):
            widget.open_calendar()
        self.assertEqual(widget.get_datetime(), datetime(2026, 8, 20, 14, 25, 0))

    def test_start_prefills_end_same_day_plus_one_hour(self) -> None:
        dialog = MeetingDialog()
        starts = datetime(2026, 8, 12, 9, 0, 0)
        dialog.starts_at_edit.set_datetime(starts)
        ends = dialog.ends_at_edit.get_datetime()
        self.assertEqual(ends, datetime(2026, 8, 12, 10, 0, 0))
        self.assertEqual(ends.date(), starts.date())
        dialog.close()

    def test_manual_end_not_overwritten_on_start_change(self) -> None:
        dialog = MeetingDialog()
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 9, 0, 0))
        dialog.ends_at_edit.set_datetime(datetime(2026, 8, 12, 15, 0, 0))
        self.assertTrue(dialog._ends_manually_edited)

        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 11, 0, 0))
        self.assertEqual(
            dialog.ends_at_edit.get_datetime(),
            datetime(2026, 8, 12, 15, 0, 0),
        )
        dialog.close()

    def test_auto_end_shifts_while_not_manual(self) -> None:
        dialog = MeetingDialog()
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 9, 0, 0))
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 11, 0, 0))
        self.assertEqual(
            dialog.ends_at_edit.get_datetime(),
            datetime(2026, 8, 12, 12, 0, 0),
        )
        dialog.close()

    def test_organizer_from_thp_and_persons(self) -> None:
        worker = settings_service.save_worker(
            first_name="Tomáš",
            last_name="THPák",
            position="Technik BOZP",
        )
        organizer = MeetingOrganizerWidget()
        organizer.thp_selector.set_person_id(worker.id)
        organizer._on_thp_changed()
        person_id = organizer.current_person_id()
        self.assertIsNotNone(person_id)
        person = person_service.get_by_id(person_id)
        self.assertEqual(person.first_name, "Tomáš")
        self.assertEqual(person.last_name, "THPák")
        self.assertTrue(person.is_employee)

        external = person_service.create_person(
            first_name="Eva",
            last_name="Externí",
            job_title="Konzultant",
        )
        organizer.set_person_id(external.id)
        self.assertEqual(organizer.current_person_id(), external.id)
        self.assertIsNone(organizer.thp_selector.current_person_id())
        self.assertFalse(organizer.person_label.isHidden())
        self.assertIn("Eva Externí", organizer.person_label.text())

    def test_participants_from_thp_and_persons_dedup(self) -> None:
        worker = settings_service.save_worker(
            first_name="Petr",
            last_name="Účastník",
            position="Mistr",
        )
        linked = ensure_person_for_thp_worker(worker)
        other = person_service.create_person(
            first_name="Jana",
            last_name="Host",
            organization="Dodavatel s.r.o.",
        )

        widget = MeetingParticipantsWidget()
        widget._append_person_id(linked.id)
        widget._append_person_id(other.id)
        widget._append_person_id(linked.id)  # duplicita
        self.assertEqual(widget.selected_person_ids(), [linked.id, other.id])

        labels = [
            widget.list_widget.item(i).text()
            for i in range(widget.list_widget.count())
        ]
        self.assertTrue(any("Petr Účastník" in text for text in labels))
        self.assertTrue(any("Mistr" in text or "Dodavatel" in text for text in labels))

        # stejná osoba přes THP i Osoby → jedno person_id
        again = ensure_person_for_thp_worker(worker)
        self.assertEqual(again.id, linked.id)
        widget._append_person_id(again.id)
        self.assertEqual(widget.selected_person_ids(), [linked.id, other.id])

    def test_legacy_persons_load_in_dialog(self) -> None:
        organizer = person_service.create_person(first_name="Legacy", last_name="Organizátor")
        participant = person_service.create_person(first_name="Legacy", last_name="Účastník")
        meeting = meeting_service.create_meeting(
            title="Starší záznam",
            organizer_person_id=organizer.id,
            participant_ids=[participant.id],
            starts_at=datetime(2026, 8, 12, 9, 0, 0),
            ends_at=datetime(2026, 8, 12, 11, 30, 0),
        )
        dialog = MeetingDialog(meeting=meeting)
        self.assertEqual(dialog.organizer_selector.current_person_id(), organizer.id)
        self.assertEqual(
            dialog.participants_selector.selected_person_ids(),
            [participant.id],
        )
        # ukončení z DB se při změně zahájení nepřepíše
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 10, 0, 0))
        self.assertEqual(
            dialog.ends_at_edit.get_datetime(),
            datetime(2026, 8, 12, 11, 30, 0),
        )
        dialog.close()

    def test_pick_dialogs_exist(self) -> None:
        self.assertTrue(issubclass(_SinglePersonPickDialog, QDialog))
        self.assertTrue(issubclass(_MultiThpPickDialog, QDialog))
        self.assertTrue(issubclass(_MultiPersonPickDialog, QDialog))
        self.assertIsNotNone(find_person_matching_thp)


if __name__ == "__main__":
    unittest.main()
