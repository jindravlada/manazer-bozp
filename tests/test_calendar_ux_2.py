"""CALENDAR-UX-2: delší a stabilní tooltip kalendáře."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtWidgets import QApplication, QToolTip

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
        TaskCalendarWidget,
        _TOOLTIP_DURATION_MS,
        build_calendar_day_data,
    )
    from core.widgets.persistent_tooltips import TOOLTIP_DISPLAY_MS
    from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class CalendarUx2TestCase(unittest.TestCase):
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

    def _calendar_with_events(self) -> TaskCalendarWidget:
        meeting_service.create_meeting(
            title="Den deset A",
            starts_at=datetime(2026, 8, 10, 7, 0),
            ends_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        meeting_service.create_meeting(
            title="Den deset B",
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
        self.assertIsNotNone(cal._view)
        return cal

    def _center_for_day(self, cal: TaskCalendarWidget, day_number: int) -> QPoint:
        view = cal._view
        assert view is not None
        model = view.model()
        for row in range(model.rowCount()):
            for col in range(model.columnCount()):
                idx = model.index(row, col)
                if str(idx.data()) == str(day_number):
                    center = view.visualRect(idx).center()
                    mapped = cal._date_at(center)
                    if mapped and mapped.month == 8 and mapped.day == day_number:
                        return center
        self.fail(f"cell for day {day_number} not found")

    def test_tooltip_duration_at_least_15_seconds(self) -> None:
        self.assertEqual(_TOOLTIP_DURATION_MS, TOOLTIP_DISPLAY_MS)
        self.assertGreaterEqual(_TOOLTIP_DURATION_MS, 15_000)
        cal = self._calendar_with_events()
        pos = self._center_for_day(cal, 10)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=False
        ):
            cal._update_day_tooltip(pos)
            self.assertEqual(show_text.call_count, 1)
            args = show_text.call_args.args
            self.assertGreaterEqual(len(args), 5)
            self.assertGreaterEqual(args[4], 15_000)
            self.assertIn("Den deset A", args[1])
            self.assertIn("Den deset B", args[1])

    def test_move_inside_same_day_does_not_recreate(self) -> None:
        cal = self._calendar_with_events()
        view = cal._view
        assert view is not None
        pos = self._center_for_day(cal, 10)
        rect = view.visualRect(view.indexAt(pos))
        pos_a = rect.center()
        pos_b = QPoint(rect.center().x() + 2, rect.center().y() + 1)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=False
        ):
            cal._update_day_tooltip(pos_a)
            self.assertEqual(show_text.call_count, 1)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=True
        ):
            cal._update_day_tooltip(pos_b)
            cal._update_day_tooltip(pos_a)
            show_text.assert_not_called()
            self.assertEqual(cal._tooltip_date, date(2026, 8, 10))

    def test_leave_cell_hides_tooltip(self) -> None:
        cal = self._calendar_with_events()
        pos = self._center_for_day(cal, 10)
        with patch.object(QToolTip, "isVisible", return_value=False):
            cal._update_day_tooltip(pos)
        self.assertEqual(cal._tooltip_date, date(2026, 8, 10))

        with patch.object(QToolTip, "hideText") as hide_text:
            leave = QEvent(QEvent.Type.Leave)
            cal.eventFilter(cal._view.viewport(), leave)
            hide_text.assert_called()
            self.assertIsNone(cal._tooltip_date)

    def test_switch_day_shows_new_tooltip(self) -> None:
        cal = self._calendar_with_events()
        pos10 = self._center_for_day(cal, 10)
        pos11 = self._center_for_day(cal, 11)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=False
        ):
            cal._update_day_tooltip(pos10)
            self.assertEqual(cal._tooltip_date, date(2026, 8, 10))
            self.assertIn("Den deset A", show_text.call_args.args[1])

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=True
        ):
            cal._update_day_tooltip(pos11)
            self.assertEqual(show_text.call_count, 1)
            self.assertEqual(cal._tooltip_date, date(2026, 8, 11))
            text = show_text.call_args.args[1]
            self.assertIn("Den jedenáct", text)
            self.assertNotIn("Den deset A", text)
            self.assertGreaterEqual(show_text.call_args.args[4], 15_000)

    def test_reshow_after_hide_on_same_day(self) -> None:
        """Po skrytí (timeout) smí stejný den tooltip znovu zobrazit."""
        cal = self._calendar_with_events()
        pos = self._center_for_day(cal, 10)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=False
        ):
            cal._update_day_tooltip(pos)
            self.assertEqual(show_text.call_count, 1)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "isVisible", return_value=False
        ):
            cal._update_day_tooltip(pos)
            self.assertEqual(show_text.call_count, 1)
            self.assertGreaterEqual(show_text.call_args.args[4], 15_000)


if __name__ == "__main__":
    unittest.main()
