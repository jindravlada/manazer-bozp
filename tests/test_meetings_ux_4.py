"""EVENTS-UX-4: ergonomie editoru Událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCompleter

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
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.widgets.nullable_date_edit import NullableDateEdit, parse_czech_date
    from core.widgets.nullable_time_edit import NullableTimeEdit, parse_czech_time
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.schuzky.constants import DEFAULT_MEETING_STATUS, TAB_DISCUSSION, TAB_MEETING
    from moduly.schuzky.sluzby.meeting_person_link import ensure_person_for_thp_worker
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.event_datetime_fields import EventDateTimeFields
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_people_widgets import (
        MeetingOrganizerWidget,
        MeetingParticipantsWidget,
        MeetingPersonTypeahead,
    )
    from moduly.schuzky.ui.schuzky_page import SchuzkyPage


class EventsUx4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_tab_renamed_to_zapisky(self) -> None:
        self.assertEqual(TAB_DISCUSSION, "Zápisky")
        dialog = MeetingDialog()
        titles = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertEqual(titles, [TAB_MEETING, "Zápisky"])
        dialog.close()

    def test_date_keyboard_parsing(self) -> None:
        today = date(2026, 8, 4)
        self.assertEqual(parse_czech_date("10.8.2026", today=today), date(2026, 8, 10))
        self.assertEqual(parse_czech_date("10.8.", today=today), date(2026, 8, 10))
        self.assertEqual(parse_czech_date("10.8", today=today), date(2026, 8, 10))
        self.assertEqual(parse_czech_date("10", today=today), date(2026, 8, 10))
        self.assertEqual(parse_czech_date("10.", today=today), date(2026, 8, 10))

        edit = NullableDateEdit()
        edit.line_edit.setText("10.8.2026")
        edit._normalize_input()
        self.assertEqual(edit.get_date(), date(2026, 8, 10))
        self.assertEqual(edit.line_edit.text(), "10.08.2026")

    def test_time_keyboard_parsing(self) -> None:
        self.assertEqual(parse_czech_time("9"), time(9, 0))
        self.assertEqual(parse_czech_time("9:30"), time(9, 30))
        self.assertEqual(parse_czech_time("930"), time(9, 30))
        self.assertEqual(parse_czech_time("14:05"), time(14, 5))

        edit = NullableTimeEdit()
        edit.line_edit.setText("9:30")
        edit._normalize_input()
        self.assertEqual(edit.get_time(), time(9, 30))
        self.assertEqual(edit.line_edit.text(), "09:30")

    def test_separate_date_and_time_fields(self) -> None:
        fields = EventDateTimeFields()
        self.assertIsInstance(fields.date_edit, NullableDateEdit)
        self.assertIsInstance(fields.time_edit, NullableTimeEdit)
        fields.set_datetime(datetime(2026, 8, 12, 9, 0))
        self.assertEqual(fields.date_edit.get_date(), date(2026, 8, 12))
        self.assertEqual(fields.time_edit.get_time(), time(9, 0))

        # změna data nepřepíše čas
        fields.date_edit.set_date_value(date(2026, 8, 20))
        self.assertEqual(fields.time_edit.get_time(), time(9, 0))
        self.assertEqual(fields.get_datetime(), datetime(2026, 8, 20, 9, 0))

    def test_calendar_is_helper_only(self) -> None:
        edit = NullableDateEdit()
        with patch.object(edit, "open_calendar") as open_calendar:
            edit.calendar_button.click()
            open_calendar.assert_called()
        # bez výběru v kalendáři zůstane prázdné
        with patch("core.widgets.nullable_date_edit.QDialog.exec", return_value=0):
            edit.open_calendar()
        self.assertIsNone(edit.get_date())

    def test_auto_end_and_manual_lock(self) -> None:
        dialog = MeetingDialog()
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 9, 0))
        self.assertEqual(
            dialog.ends_at_edit.get_datetime(),
            datetime(2026, 8, 12, 10, 0),
        )
        dialog.ends_at_edit.set_datetime(datetime(2026, 8, 13, 15, 0))
        dialog.starts_at_edit.set_datetime(datetime(2026, 8, 12, 11, 0))
        self.assertEqual(
            dialog.ends_at_edit.get_datetime(),
            datetime(2026, 8, 13, 15, 0),
        )
        dialog.close()

    def test_organizer_typeahead(self) -> None:
        worker = settings_service.save_worker(
            first_name="Vladimír",
            last_name="Jindra",
            title_before="Ing.",
        )
        person = ensure_person_for_thp_worker(worker)
        organizer = MeetingOrganizerWidget()
        completer = organizer.typeahead.completer()
        self.assertIsInstance(completer, QCompleter)
        self.assertEqual(completer.filterMode(), Qt.MatchFlag.MatchContains)

        labels = [organizer.typeahead.itemText(i) for i in range(organizer.typeahead.count())]
        self.assertTrue(any("Jindra" in label for label in labels))
        organizer.set_person_id(person.id)
        self.assertEqual(organizer.current_person_id(), person.id)
        self.assertTrue(organizer.from_persons_btn.isVisibleTo(organizer) or not organizer.from_persons_btn.isHidden())

    def test_participants_typeahead_and_dedup(self) -> None:
        worker = settings_service.save_worker(first_name="Petr", last_name="Host")
        linked = ensure_person_for_thp_worker(worker)
        other = person_service.create_person(first_name="Jana", last_name="Externí")

        widget = MeetingParticipantsWidget()
        self.assertIsInstance(widget.typeahead, MeetingPersonTypeahead)
        widget.typeahead.set_person_id(linked.id)
        widget._add_current()
        widget.typeahead.set_person_id(other.id)
        widget._add_current()
        widget.typeahead.set_person_id(linked.id)
        widget._add_current()
        self.assertEqual(widget.selected_person_ids(), [linked.id, other.id])

    def test_saved_event_appears_on_dashboard_after_refresh(self) -> None:
        page = SchuzkyPage()
        upcoming = UpcomingTasksWidget()
        refreshed: list[str] = []

        def _refresh() -> None:
            upcoming.refresh()
            refreshed.append("ok")

        page.set_dashboard_refresh_callback(_refresh)

        starts = datetime.now() + timedelta(days=2, hours=3)
        meeting = meeting_service.create_meeting(
            title="Dashboard ihned",
            starts_at=starts,
            status=DEFAULT_MEETING_STATUS,
        )
        page._refresh_dashboard()
        self.assertEqual(refreshed, ["ok"])

        found = False
        for row in range(upcoming.table.rowCount()):
            payload = upcoming.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                found = True
                break
        self.assertTrue(found)

        items = [
            item
            for item in get_attention_items()
            if item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id
        ]
        self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
