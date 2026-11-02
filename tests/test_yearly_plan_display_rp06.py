"""RP-06: Agenda a Dashboard ukazují jen skutečné úkoly a události."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()
_TODAY = date(2026, 11, 2)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_PERIODIC, ITEM_TYPE_YEARLY_PLAN_MONTH
    from core.dashboard.attention_service import (
        get_attention_items,
        get_periodic_reminder_items,
        get_yearly_plan_month_reminder_items,
    )
    from core.dashboard.widget_calendar_placeholder import (
        CalendarPlaceholderWidget,
        periodic_calendar_marks,
    )
    from core.dashboard.widget_today import TodayWidget
    from core.database.session import get_session
    from core.shared.task_source_display import task_source_label, task_source_short_label
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import ITEM_TYPE_MEETING, ITEM_TYPE_TASK, SOURCE_LABEL_MEETING
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import UNIT_MONTHS
    from moduly.periodicke_cinnosti.modely.periodic_calendar_occurrence import (
        PeriodicCalendarOccurrence,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar_occurrence_service import (
        get_occurrence,
        link_meeting,
        link_task,
        skip_occurrence,
    )
    from moduly.rocni_plan.constants import (
        DISPLAY_PLANNED,
        DISPLAY_TO_PLAN,
        SOURCE_MODULE_YEARLY_PLAN,
        month_planning_attention_title,
        planning_remaining_phrase,
    )
    from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
    from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove
    from moduly.rocni_plan.modely.yearly_plan_occurrence import YearlyPlanOccurrence
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class YearlyPlanDisplayRp06TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(PeriodicCalendarOccurrence))
            session.execute(delete(YearlyPlanOccurrence))
            session.execute(delete(YearlyPlanItemMove))
            session.execute(delete(YearlyPlanItem))
            session.commit()
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

    def _activity(self, title: str, *, due: date = date(2026, 11, 5)):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=due,
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            notify_every=14,
            calendar_start_year=2026,
            calendar_start_month=11,
            calendar_interval_months=1,
        )

    def _agenda(self):
        return agenda_service.get_items(
            today=_TODAY,
            now=datetime(2026, 11, 2, 8, 0),
        )

    def _rows(self, title: str, *, year: int = 2026, month: int = 11):
        return [
            row
            for row in yearly_plan_service.list_month_rows(year, month, today=_TODAY)
            if row.title == title
        ]

    def test_calculated_periodic_term_is_not_an_agenda_task(self) -> None:
        activity = self._activity("Kontrola lékárničky")
        titles = [
            item.title
            for item in self._agenda()
            if item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity.id
        ]
        self.assertEqual(titles, [])
        self.assertNotIn("Kontrola lékárničky", [item.title for item in self._agenda()])

    def test_real_task_and_event_from_yearly_plan_stay_in_agenda(self) -> None:
        task_activity = self._activity("Školení BOZP")
        meeting_activity = self._activity("Porada vedení")
        task = task_service.create_task(
            title="Školení BOZP",
            due_date=date(2026, 11, 10),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=task_activity.id,
            requires_verification=False,
        )
        meeting = meeting_service.create_meeting(
            title="Porada vedení",
            starts_at=datetime(2026, 11, 12, 9, 0),
        )
        link_task(
            task_activity.id,
            original_year=2026,
            original_month=11,
            task_id=task.id,
        )
        link_meeting(
            meeting_activity.id,
            original_year=2026,
            original_month=11,
            meeting_id=meeting.id,
        )

        tasks = [
            item
            for item in self._agenda()
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        meetings = [
            item
            for item in self._agenda()
            if item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting.id
        ]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].source, "Roční plán")
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0].source, "Roční plán")
        self.assertEqual(task_source_short_label(task), "Roční plán")
        self.assertEqual(task_source_label(task), "Roční plán")
        self.assertEqual(task.source_module, SOURCE_MODULE_YEARLY_PLAN)
        self.assertEqual(task.source_record_id, task_activity.id)
        stored = get_occurrence(task_activity.id, 2026, 11)
        self.assertEqual(stored.task_id, task.id)
        self.assertIsNone(stored.meeting_id)

    def test_automatic_terms_leave_upcoming_and_burning(self) -> None:
        activity = self._activity("Automatický termín")
        upcoming = get_attention_items(today=_TODAY)
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity.id
                for item in upcoming
            )
        )
        self.assertEqual(get_periodic_reminder_items(today=_TODAY), [])
        widget = TodayWidget()
        widget.refresh(today=_TODAY)
        self.assertNotIn("Automatický termín", widget.content.text())
        widget.close()

    def test_unprocessed_month_warning_counts_and_opens_month(self) -> None:
        self._activity("Kontrola lékárničky")
        yearly_plan_service.create(year=2026, month=11, title="Ruční A")
        yearly_plan_service.create(year=2026, month=11, title="Ruční B")
        self.assertEqual(
            get_yearly_plan_month_reminder_items(today=date(2026, 11, 1)),
            [],
        )
        items = get_yearly_plan_month_reminder_items(today=_TODAY)
        title = month_planning_attention_title(2026, 11, 3)
        self.assertEqual(
            title,
            "Roční plán – listopad 2026: zbývají 3 činnosti k naplánování.",
        )
        self.assertEqual([item.title for item in items], [title])
        self.assertEqual(items[0].item_type, ITEM_TYPE_YEARLY_PLAN_MONTH)
        self.assertEqual(items[0].open_metadata["year"], 2026)
        self.assertEqual(items[0].open_metadata["month"], 11)
        self.assertTrue(
            any(item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH for item in get_attention_items(today=_TODAY))
        )

        window = MagicMock()
        MainWindow._open_attention_item(window, items[0])
        window._open_yearly_plan_month.assert_called_once_with(2026, 11)
        page = AgendaPage()
        page.open_yearly_plan(2026, 11)
        self.assertEqual(page.yearly_plan_tab.current_year(), 2026)
        self.assertEqual(page.yearly_plan_tab.current_month(), 11)
        page.close()

        widget = TodayWidget()
        widget.refresh(today=_TODAY)
        self.assertIn(title, widget.content.text())
        widget.close()

    def test_warning_disappears_when_month_is_decided(self) -> None:
        activity = self._activity("Ještě k naplánování")
        first = yearly_plan_service.create(year=2026, month=11, title="Ruční A")
        second = yearly_plan_service.create(year=2026, month=11, title="Ruční B")
        self.assertEqual(len(get_yearly_plan_month_reminder_items(today=_TODAY)), 1)
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=11,
            reason="Letos bez kontroly.",
        )
        yearly_plan_service.skip_manual(first.id, reason="Není třeba.")
        yearly_plan_service.skip_manual(second.id, reason="Není třeba.")
        self.assertEqual(get_yearly_plan_month_reminder_items(today=_TODAY), [])

    def test_completing_task_does_not_change_yearly_plan(self) -> None:
        activity = self._activity("Školení BOZP")
        task = task_service.create_task(
            title="Školení BOZP",
            due_date=date(2026, 11, 10),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=activity.id,
            requires_verification=False,
        )
        link_task(activity.id, original_year=2026, original_month=11, task_id=task.id)
        self.assertEqual(self._rows("Školení BOZP")[0].display_status, DISPLAY_PLANNED)
        task_service.mark_completed(task.id)
        reloaded = task_service.get_task_by_id(task.id)
        self.assertTrue(reloaded.completed)
        self.assertEqual(reloaded.source_module, SOURCE_MODULE_YEARLY_PLAN)
        self.assertEqual(reloaded.source_record_id, activity.id)
        row = self._rows("Školení BOZP")[0]
        self.assertEqual(row.display_status, DISPLAY_PLANNED)
        self.assertNotEqual(row.display_status, DISPLAY_TO_PLAN)
        stored = get_occurrence(activity.id, 2026, 11)
        self.assertEqual(stored.task_id, task.id)

    def test_calendar_keeps_real_work_and_drops_periodic_marks(self) -> None:
        self._activity("Kontrola lékárničky", due=date(2026, 11, 5))
        task_service.create_task(title="Skutečný úkol", due_date=date(2026, 11, 10))
        meeting_service.create_meeting(
            title="Skutečná událost",
            starts_at=datetime(2026, 11, 12, 9, 0),
        )
        self.assertEqual(periodic_calendar_marks(2026, 11, today=_TODAY), ({}, {}))
        panel = CalendarPlaceholderWidget()
        panel.calendar.setCurrentPage(2026, 11)
        self.assertNotIn(date(2026, 11, 5), panel.calendar._task_dates)
        self.assertIn(date(2026, 11, 10), panel.calendar._task_dates)
        self.assertIn(date(2026, 11, 12), panel.calendar._task_dates)
        tooltip = "\n".join(panel.calendar._day_events.get(date(2026, 11, 5), []))
        self.assertNotIn("Kontrola lékárničky", tooltip)
        self.assertIn(
            "Skutečný úkol",
            "\n".join(panel.calendar._day_events[date(2026, 11, 10)]),
        )
        self.assertIn(
            "Skutečná událost",
            "\n".join(panel.calendar._day_events[date(2026, 11, 12)]),
        )
        panel.close()

    def test_other_sources_keep_their_labels(self) -> None:
        plain = meeting_service.create_meeting(
            title="Běžná porada",
            starts_at=datetime(2026, 11, 18, 9, 0),
        )
        injury = task_service.create_task(
            title="Opatření z úrazu",
            due_date=date(2026, 11, 20),
            source_module="kniha_urazu",
        )
        meetings = [
            item
            for item in self._agenda()
            if item.item_type == ITEM_TYPE_MEETING and item.source_id == plain.id
        ]
        tasks = [
            item
            for item in self._agenda()
            if item.item_type == ITEM_TYPE_TASK and item.source_id == injury.id
        ]
        self.assertEqual(meetings[0].source, SOURCE_LABEL_MEETING)
        self.assertEqual(tasks[0].source, "Úrazy")
        self.assertEqual(injury.source_module, "kniha_urazu")

    def test_remaining_phrase_uses_czech_counts(self) -> None:
        self.assertEqual(planning_remaining_phrase(1), "zbývá 1 činnost k naplánování")
        self.assertEqual(
            planning_remaining_phrase(3),
            "zbývají 3 činnosti k naplánování",
        )
        self.assertEqual(
            planning_remaining_phrase(5),
            "zbývá 5 činností k naplánování",
        )


if __name__ == "__main__":
    unittest.main()
