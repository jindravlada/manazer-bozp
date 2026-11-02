"""PC-02: periodické činnosti v Agendě, Nadcházejících, Co hoří a kalendáři."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()
_TODAY = date(2026, 11, 1)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_PERIODIC
    from core.dashboard.attention_service import (
        get_attention_items,
        get_periodic_reminder_items,
    )
    from core.dashboard.widget_calendar_placeholder import (
        CalendarPlaceholderWidget,
        periodic_calendar_marks,
    )
    from core.dashboard.widget_today import TodayWidget
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import COL_TITLE, ITEM_TYPE_MEETING, ITEM_TYPE_TASK
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import UNIT_MONTHS, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.rocni_plan.constants import DISPLAY_TO_PLAN
    from moduly.rocni_plan.sluzby.yearly_plan_service import list_periodic_rows_for_month
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class PeriodicDisplayPc02TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for activity in list(periodic_activity_service.get_all()):
            periodic_activity_service.update_activity(
                activity.id,
                title=f"OLD-{activity.id}-{activity.title}",
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )

    def _create(self, *, title: str, due: date, unit: str = UNIT_YEARS, active: bool = True):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=due,
            repeat_every=1,
            repeat_unit=unit,
            notify_every=0,
            active=active,
        )

    def _agenda_dates(self, activity_id: int) -> list[date]:
        return [
            item.due_date
            for item in agenda_service.get_items(today=_TODAY, now=datetime(2026, 11, 1, 8, 0))
            if item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity_id
        ]

    def _upcoming_dates(self, activity_id: int) -> list[date]:
        return [
            item.date
            for item in get_attention_items(today=_TODAY)
            if item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity_id
        ]

    def _reminder_dates(self, activity_id: int) -> list[date]:
        return [
            item.date
            for item in get_periodic_reminder_items(today=_TODAY)
            if item.source_id == activity_id
        ]

    def test_overdue_today_two_months_and_four_months(self) -> None:
        overdue = self._create(title="Po splatnosti", due=date(2026, 10, 5))
        today_item = self._create(title="Termín dnes", due=_TODAY)
        in_two = self._create(title="Za dva měsíce", due=date(2027, 1, 1))
        in_four = self._create(title="Za čtyři měsíce", due=date(2027, 3, 1))

        self.assertEqual(self._agenda_dates(overdue.id), [date(2026, 10, 5)])
        self.assertEqual(self._upcoming_dates(overdue.id), [date(2026, 10, 5)])
        self.assertEqual(self._reminder_dates(overdue.id), [date(2026, 10, 5)])

        self.assertEqual(self._agenda_dates(today_item.id), [_TODAY])
        self.assertEqual(self._upcoming_dates(today_item.id), [_TODAY])
        self.assertEqual(self._reminder_dates(today_item.id), [_TODAY])

        self.assertEqual(self._agenda_dates(in_two.id), [date(2027, 1, 1)])
        self.assertEqual(self._upcoming_dates(in_two.id), [date(2027, 1, 1)])
        self.assertEqual(self._reminder_dates(in_two.id), [])

        self.assertEqual(self._agenda_dates(in_four.id), [])
        self.assertEqual(self._upcoming_dates(in_four.id), [])
        self.assertEqual(self._reminder_dates(in_four.id), [])

        marks, events = periodic_calendar_marks(2027, 3, today=_TODAY)
        self.assertEqual(marks[date(2027, 3, 1)], {"future"})
        self.assertIn("Za čtyři měsíce", "\n".join(events[date(2027, 3, 1)]))
        self.assertNotIn("overdue", marks[date(2027, 3, 1)])

        today_marks, _ = periodic_calendar_marks(2026, 11, today=_TODAY)
        self.assertEqual(today_marks[_TODAY], {"today"})
        self.assertNotIn(date(2026, 10, 5), today_marks)
        october, _ = periodic_calendar_marks(2026, 10, today=_TODAY)
        self.assertEqual(october[date(2026, 10, 5)], {"overdue"})

    def test_distant_calendar_month_and_single_overdue(self) -> None:
        distant = self._create(
            title="Vzdálený měsíc",
            due=date(2026, 11, 15),
            unit=UNIT_MONTHS,
        )
        stale = self._create(
            title="Dlouho po termínu",
            due=date(2024, 1, 5),
            unit=UNIT_MONTHS,
        )
        before = periodic_activity_service.list_occurrences(stale.id)

        stale_dates = self._agenda_dates(stale.id)
        self.assertEqual(
            [item for item in stale_dates if item < _TODAY],
            [date(2024, 1, 5)],
        )
        self.assertEqual(
            [item for item in stale_dates if item >= _TODAY],
            [date(2026, 11, 5), date(2026, 12, 5), date(2027, 1, 5)],
        )
        self.assertEqual(stale_dates, sorted(stale_dates))
        self.assertEqual(len(stale_dates), len(set(stale_dates)))
        self.assertNotIn(date(2025, 3, 5), stale_dates)
        self.assertEqual(self._upcoming_dates(stale.id), stale_dates)
        self.assertEqual(self._reminder_dates(stale.id), [date(2024, 1, 5)])

        plan = [
            row
            for row in list_periodic_rows_for_month(2025, 3, today=_TODAY)
            if row.activity_id == stale.id
        ]
        self.assertEqual(
            [(row.planned_due_date, row.display_status) for row in plan],
            [(date(2025, 3, 5), DISPLAY_TO_PLAN)],
        )

        marks, _ = periodic_calendar_marks(2030, 6, today=_TODAY)
        self.assertEqual(marks[date(2030, 6, 15)], {"future"})
        self.assertNotIn(date(2030, 6, 15), self._agenda_dates(distant.id))
        self.assertEqual(periodic_activity_service.list_occurrences(stale.id), before)

        panel = CalendarPlaceholderWidget()
        panel.calendar.setCurrentPage(2030, 6)
        self.assertIn("future", panel.calendar._task_dates.get(date(2030, 6, 15), set()))
        panel.close()

    def test_repeated_performance_and_completed_occurrence(self) -> None:
        activity = self._create(
            title="Opakované provedení",
            due=date(2026, 11, 5),
            unit=UNIT_MONTHS,
        )
        for performed in (date(2026, 10, 6), date(2026, 10, 29), date(2026, 11, 2)):
            periodic_activity_service.record_performance(
                activity.id,
                performed_at=performed,
                result_note=performed.isoformat(),
            )
        stored = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(stored.next_due_date, date(2026, 12, 5))
        self.assertEqual(len(periodic_activity_service.list_occurrences(activity.id)), 3)

        self.assertEqual(
            self._agenda_dates(activity.id),
            [date(2026, 12, 5), date(2027, 1, 5)],
        )
        self.assertNotIn(date(2026, 11, 5), self._agenda_dates(activity.id))
        self.assertEqual(self._agenda_dates(activity.id).count(date(2026, 12, 5)), 1)
        self.assertEqual(self._reminder_dates(activity.id), [])

        november, _ = periodic_calendar_marks(2026, 11, today=_TODAY)
        self.assertEqual(november[date(2026, 11, 5)], {"done"})
        self.assertNotIn("overdue", november[date(2026, 11, 5)])
        self.assertNotIn("future", november[date(2026, 11, 5)])
        december, _ = periodic_calendar_marks(2026, 12, today=_TODAY)
        self.assertEqual(december[date(2026, 12, 5)], {"future"})

    def test_inactive_is_hidden(self) -> None:
        activity = self._create(title="Neaktivní", due=_TODAY, active=False)
        self.assertEqual(self._agenda_dates(activity.id), [])
        self.assertEqual(self._upcoming_dates(activity.id), [])
        self.assertEqual(self._reminder_dates(activity.id), [])
        marks, _ = periodic_calendar_marks(2026, 11, today=_TODAY)
        self.assertNotIn(_TODAY, marks)

    def test_click_opens_activity_and_keeps_other_items(self) -> None:
        opened_on = date.today()
        activity = self._create(title="Otevřít činnost", due=opened_on)
        task = task_service.create_task(title="Úkol zůstává", due_date=opened_on)
        meeting = meeting_service.create_meeting(
            title="Událost zůstává",
            starts_at=datetime(opened_on.year, opened_on.month, opened_on.day, 9, 0),
        )
        items = agenda_service.get_items(
            today=opened_on,
            now=datetime(opened_on.year, opened_on.month, opened_on.day, 8, 0),
        )
        pairs = {(item.item_type, item.source_id) for item in items}
        self.assertIn((ITEM_TYPE_TASK, task.id), pairs)
        self.assertIn((ITEM_TYPE_MEETING, meeting.id), pairs)
        self.assertIn((ITEM_TYPE_PERIODIC, activity.id), pairs)

        opened: list = []
        page = AgendaPage(open_attention_callback=opened.append)
        self.assertEqual(set(page.type_checks), {ITEM_TYPE_TASK, ITEM_TYPE_MEETING})
        page.refresh()
        selected = False
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and payload.item_type == ITEM_TYPE_PERIODIC
                and payload.source_id == activity.id
            ):
                page.table.selectRow(row)
                selected = True
                break
        self.assertTrue(selected)
        page.edit_selected()
        self.assertEqual(opened[-1].source_id, activity.id)
        self.assertEqual(opened[-1].item_type, ITEM_TYPE_PERIODIC)

        window = MagicMock()
        MainWindow._open_attention_item(window, opened[-1])
        window._open_periodic_activity_by_id.assert_called_once_with(activity.id)
        page.close()

        upcoming_opened: list = []
        widget = UpcomingTasksWidget(open_attention_callback=upcoming_opened.append)
        widget.refresh()
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == activity.id:
                widget.table.selectRow(row)
                break
        widget.open_button.click()
        self.assertEqual(upcoming_opened[-1].source_id, activity.id)
        widget.close()

    def test_burning_panel_keeps_reminder_window(self) -> None:
        self._create(title="Hoří po termínu", due=date(2026, 10, 5))
        self._create(title="Hoří dnes", due=_TODAY)
        self._create(title="Nehoří za dva měsíce", due=date(2027, 1, 1))
        self._create(title="Nehoří za čtyři měsíce", due=date(2027, 3, 1))

        widget = TodayWidget()
        widget.refresh(today=_TODAY)
        text = widget.content.text()
        self.assertIn("Hoří po termínu", text)
        self.assertIn("05.10.2026", text)
        self.assertIn("Hoří dnes", text)
        self.assertNotIn("Nehoří za dva měsíce", text)
        self.assertNotIn("Nehoří za čtyři měsíce", text)
        widget.close()


if __name__ == "__main__":
    unittest.main()
