"""CALENDAR-UX-1: události a oprava tooltipů kalendáře."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint
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

    from core.dashboard.widget_calendar_placeholder import (
        CalendarPlaceholderWidget,
        TaskCalendarWidget,
        build_calendar_day_data,
    )
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class CalendarUx1TestCase(unittest.TestCase):
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
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )
        for task in list(task_service.get_all_tasks()):
            if task.computed_status != "Zrušeno":
                task_service.cancel_task(task.id)

    def test_meetings_create_dots(self) -> None:
        day = date(2026, 8, 10)
        meeting_service.create_meeting(
            title="Školení pohyb v kolejišti",
            event_type="Školení",
            starts_at=datetime(2026, 8, 10, 7, 0),
            ends_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        task_dates, _ = build_calendar_day_data(today=date(2026, 8, 1))
        self.assertIn(day, task_dates)
        self.assertTrue(task_dates[day])

        panel = CalendarPlaceholderWidget()
        panel.refresh()
        self.assertIn(day, panel.calendar._task_dates)

    def test_tooltip_matches_hovered_day(self) -> None:
        meeting_service.create_meeting(
            title="Den deset",
            starts_at=datetime(2026, 8, 10, 9, 0),
            ends_at=datetime(2026, 8, 10, 10, 0),
            status=STATUS_PLANNED,
        )
        meeting_service.create_meeting(
            title="Den jedenáct",
            starts_at=datetime(2026, 8, 11, 9, 0),
            ends_at=datetime(2026, 8, 11, 10, 0),
            status=STATUS_PLANNED,
        )
        cal = TaskCalendarWidget()
        cal.setCurrentPage(2026, 8)
        cal.show()
        dots, events = build_calendar_day_data(today=date(2026, 8, 1))
        cal.set_task_dates(dots)
        cal.set_day_events(events)
        cal._ensure_tooltip_hook()
        view = cal._view
        self.assertIsNotNone(view)

        def _center_for_day(day_number: int) -> QPoint:
            model = view.model()
            for row in range(model.rowCount()):
                for col in range(model.columnCount()):
                    idx = model.index(row, col)
                    if str(idx.data()) == str(day_number):
                        mapped = cal._date_at(view.visualRect(idx).center())
                        if mapped and mapped.month == 8 and mapped.day == day_number:
                            return view.visualRect(idx).center()
            self.fail(f"cell for day {day_number} not found")

        pos10 = _center_for_day(10)
        self.assertEqual(cal._date_at(pos10), date(2026, 8, 10))
        cal._update_day_tooltip(pos10)
        self.assertEqual(cal._tooltip_date, date(2026, 8, 10))

        pos11 = _center_for_day(11)
        self.assertEqual(cal._date_at(pos11), date(2026, 8, 11))
        cal._update_day_tooltip(pos11)
        self.assertEqual(cal._tooltip_date, date(2026, 8, 11))

    def test_tooltip_only_items_of_that_day(self) -> None:
        meeting_service.create_meeting(
            title="Ráno",
            starts_at=datetime(2026, 8, 10, 7, 0),
            ends_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        meeting_service.create_meeting(
            title="Jinde",
            starts_at=datetime(2026, 8, 12, 7, 0),
            ends_at=datetime(2026, 8, 12, 8, 0),
            status=STATUS_PLANNED,
        )
        _, events = build_calendar_day_data(today=date(2026, 8, 1))
        day_text = "\n".join(events[date(2026, 8, 10)])
        self.assertIn("Ráno", day_text)
        self.assertNotIn("Jinde", day_text)

    def test_multiple_items_same_day_chronological(self) -> None:
        meeting_service.create_meeting(
            title="Bez názvu",
            event_type="Schůzka",
            starts_at=datetime(2026, 8, 10, 8, 0),
            ends_at=datetime(2026, 8, 10, 9, 0),
            status=STATUS_PLANNED,
        )
        # empty title after create with title="" 
        meeting_service.create_meeting(
            title="",
            event_type="Schůzka",
            starts_at=datetime(2026, 8, 10, 8, 0),
            ends_at=datetime(2026, 8, 10, 9, 0),
            status=STATUS_PLANNED,
        )
        meeting_service.create_meeting(
            title="Školení pohyb v kolejišti",
            event_type="Školení",
            starts_at=datetime(2026, 8, 10, 7, 0),
            ends_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        task_service.create_task(title="Úkol stejný den", due_date=date(2026, 8, 10))

        dots, events = build_calendar_day_data(
            today=date(2026, 8, 1),
            now=datetime(2026, 8, 1, 12, 0),
        )
        day = date(2026, 8, 10)
        self.assertIn(day, dots)
        self.assertEqual(len(dots[day]), 1)  # jedna indikace stačí (set of kinds)

        blocks = events[day]
        self.assertGreaterEqual(len(blocks), 3)
        joined = "\n\n".join(blocks)
        self.assertIn("07:00–08:00", joined)
        self.assertIn("Školení pohyb v kolejišti", joined)
        self.assertIn("Událost", joined)
        self.assertIn("Úkol", joined)
        # chronologicky: 07:00 před 08:00
        pos_7 = joined.index("07:00")
        pos_8 = joined.index("08:00–09:00")
        self.assertLess(pos_7, pos_8)

    def test_refresh_after_save(self) -> None:
        panel = CalendarPlaceholderWidget()
        day = date.today() + timedelta(days=5)
        self.assertNotIn(day, panel.calendar._task_dates)

        meeting_service.create_meeting(
            title="Po uložení",
            starts_at=datetime.combine(day, datetime.min.time().replace(hour=10)),
            ends_at=datetime.combine(day, datetime.min.time().replace(hour=11)),
            status=STATUS_PLANNED,
        )
        panel.refresh()
        self.assertIn(day, panel.calendar._task_dates)
        self.assertTrue(any("Po uložení" in "\n".join(blocks) for blocks in [panel.calendar._day_events.get(day, [])]))

        dashboard = DashboardPage()
        before = set(dashboard.calendar.calendar._task_dates.keys())
        meeting_service.create_meeting(
            title="Dashboard refresh",
            starts_at=datetime.combine(day, datetime.min.time().replace(hour=14)),
            ends_at=datetime.combine(day, datetime.min.time().replace(hour=15)),
            status=STATUS_PLANNED,
        )
        dashboard.refresh()
        self.assertIn(day, dashboard.calendar.calendar._task_dates)
        self.assertIn(
            "Dashboard refresh",
            "\n".join(dashboard.calendar.calendar._day_events.get(day, [])),
        )
        self.assertTrue(day in before or day in dashboard.calendar.calendar._task_dates)

    def test_tooltip_format(self) -> None:
        meeting_service.create_meeting(
            title="Školení pohyb v kolejišti",
            starts_at=datetime(2026, 8, 10, 7, 0),
            ends_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        _, events = build_calendar_day_data(today=date(2026, 8, 1))
        block = events[date(2026, 8, 10)][0]
        self.assertEqual(
            block,
            "• 07:00–08:00\n  Událost\n  Školení pohyb v kolejišti",
        )


if __name__ == "__main__":
    unittest.main()
