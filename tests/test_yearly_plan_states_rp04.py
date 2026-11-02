"""RP-04: jednotné stavy Ročního plánu a automatické zpracování měsíce."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_service import get_yearly_plan_month_reminder_items
    from moduly.periodicke_cinnosti.constants import UNIT_MONTHS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_calendar_occurrence_service import (
        CalendarOccurrenceError,
        move_occurrence,
        skip_occurrence,
    )
    from moduly.rocni_plan.constants import (
        DISPLAY_DONE,
        DISPLAY_PLANNED,
        DISPLAY_TO_PLAN,
        DISPLAY_WILL_NOT_PERFORM,
        STATUS_CANCELLED,
        STATUS_PLANNED,
        STATUS_VIA_TASK,
        month_planning_attention_title,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        YearlyPlanValidationError,
        resolve_display_status,
        yearly_plan_service,
    )
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class YearlyPlanStatesRp04TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        for year in range(2019, 2036):
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.repeat_every:
                    yearly_plan_service.update(
                        item.id,
                        year=item.year,
                        month=item.month,
                        title=item.title,
                        note=item.note or "",
                        status=item.status,
                        repeat_every=0,
                        repeat_unit="none",
                    )
                current = yearly_plan_service.get_by_id(item.id)
                if current is not None and current.status != STATUS_CANCELLED:
                    yearly_plan_service.cancel(current.id)
        for activity in list(periodic_activity_service.get_all(active_only=True)):
            periodic_activity_service.update_activity(
                activity.id,
                title=activity.title,
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
                note=activity.note or "",
            )

    def _rows(self, year: int, month: int, *, item_id: int | None = None, activity_id: int | None = None):
        rows = yearly_plan_service.list_month_rows(year, month, today=date(2026, 6, 1))
        if item_id is not None:
            return [row for row in rows if row.plan_item_id == item_id]
        if activity_id is not None:
            return [row for row in rows if row.activity_id == activity_id]
        return rows

    def test_new_manual_item_is_to_plan(self) -> None:
        item = yearly_plan_service.create(year=2026, month=4, title="Nová ruční")
        self.assertEqual(item.status, STATUS_PLANNED)
        self.assertEqual(item.task_id, None)
        row = self._rows(2026, 4, item_id=item.id)[0]
        self.assertEqual(row.display_status, DISPLAY_TO_PLAN)
        self.assertFalse(
            yearly_plan_service.is_month_automatically_processed(2026, 4, today=date(2026, 6, 1))
        )

    def test_manual_with_task_or_meeting_is_planned_even_when_finished(self) -> None:
        task_item = yearly_plan_service.create(year=2026, month=5, title="S úkolem")
        task = task_service.create_task(
            title="Hotový úkol",
            due_date=date(2026, 5, 10),
            completed=True,
            completed_date=date(2026, 5, 12),
        )
        linked = yearly_plan_service.link_task(task_item.id, task.id)
        self.assertEqual(linked.status, STATUS_VIA_TASK)
        self.assertEqual(task_service.get_task_by_id(task.id).computed_status, "Ukončeno")
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 8, 1)),
            DISPLAY_PLANNED,
        )
        self.assertEqual(self._rows(2026, 5, item_id=task_item.id)[0].display_status, DISPLAY_PLANNED)

        meeting_item = yearly_plan_service.create(year=2026, month=5, title="S událostí")
        start = datetime(2026, 5, 20, 9, 0)
        meeting = meeting_service.create_meeting(
            title="Událost",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        linked_meeting = yearly_plan_service.link_meeting(meeting_item.id, meeting.id)
        self.assertEqual(
            resolve_display_status(linked_meeting, today=date(2026, 5, 1)),
            DISPLAY_PLANNED,
        )
        self.assertEqual(linked_meeting.meeting_id, meeting.id)

    def test_skip_requires_reason_and_restore_keeps_links(self) -> None:
        item = yearly_plan_service.create(year=2026, month=6, title="Vynechat")
        task = task_service.create_task(title="Vazba zůstane", due_date=date(2026, 6, 2))
        yearly_plan_service.link_task(item.id, task.id)
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.skip_manual(item.id, reason="  ")
        stored = yearly_plan_service.get_by_id(item.id)
        self.assertEqual(stored.status, STATUS_VIA_TASK)
        self.assertEqual(stored.task_id, task.id)

        skipped = yearly_plan_service.skip_manual(
            item.id,
            reason="Pracoviště je uzavřené.",
        )
        self.assertEqual(skipped.status, STATUS_CANCELLED)
        self.assertEqual(skipped.skip_reason, "Pracoviště je uzavřené.")
        self.assertEqual(skipped.task_id, task.id)
        self.assertEqual(
            resolve_display_status(skipped, today=date(2026, 6, 1)),
            DISPLAY_WILL_NOT_PERFORM,
        )
        restored = yearly_plan_service.restore_manual(item.id)
        self.assertEqual(restored.status, STATUS_VIA_TASK)
        self.assertEqual(restored.skip_reason, "")
        self.assertEqual(restored.task_id, task.id)
        self.assertEqual(
            resolve_display_status(restored, today=date(2026, 6, 1)),
            DISPLAY_PLANNED,
        )

    def test_legacy_cancelled_without_reason_is_not_new_work(self) -> None:
        item = yearly_plan_service.create(year=2026, month=7, title="Staré zrušení")
        cancelled = yearly_plan_service.cancel(item.id)
        self.assertEqual(cancelled.status, STATUS_CANCELLED)
        self.assertEqual(cancelled.skip_reason, "")
        self.assertEqual(
            resolve_display_status(cancelled, today=date(2026, 12, 1)),
            DISPLAY_WILL_NOT_PERFORM,
        )
        self.assertNotEqual(
            resolve_display_status(cancelled, today=date(2026, 12, 1)),
            DISPLAY_TO_PLAN,
        )

    def test_repeating_skip_does_not_change_the_rule_or_other_months(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=1,
            title="Opakovaná",
            repeat_every=1,
            repeat_unit="months",
        )
        yearly_plan_service.skip_manual_occurrence(
            item.id,
            year=2026,
            month=3,
            reason="Jen březen.",
        )
        stored = yearly_plan_service.get_by_id(item.id)
        self.assertEqual(stored.repeat_every, 1)
        self.assertEqual(stored.repeat_unit, "months")
        self.assertEqual(stored.status, STATUS_PLANNED)
        march = self._rows(2026, 3, item_id=item.id)[0]
        april = self._rows(2026, 4, item_id=item.id)[0]
        self.assertEqual(march.display_status, DISPLAY_WILL_NOT_PERFORM)
        self.assertEqual(april.display_status, DISPLAY_TO_PLAN)
        yearly_plan_service.move_occurrence(
            item.id,
            year=2026,
            month=4,
            to_year=2026,
            to_month=5,
        )
        moved = yearly_plan_service.get_occurrence(item.id, 2026, 4)
        self.assertEqual(moved.status, STATUS_PLANNED)
        self.assertEqual(self._rows(2026, 4, item_id=item.id), [])
        self.assertEqual(self._rows(2026, 5, item_id=item.id)[0].display_status, DISPLAY_TO_PLAN)
        self.assertEqual(self._rows(2026, 3, item_id=item.id)[0].display_status, DISPLAY_WILL_NOT_PERFORM)

    def test_periodic_states_move_and_two_rows_in_one_month(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Kontrola",
            next_due_date=date(2026, 1, 15),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            calendar_start_year=2026,
            calendar_start_month=1,
            calendar_interval_months=1,
        )
        self.assertEqual(self._rows(2026, 3, activity_id=activity.id)[0].display_status, DISPLAY_TO_PLAN)
        with self.assertRaises(CalendarOccurrenceError):
            skip_occurrence(activity.id, original_year=2026, original_month=3, reason="")
        move_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            to_year=2026,
            to_month=4,
        )
        self.assertEqual(self._rows(2026, 3, activity_id=activity.id), [])
        april = self._rows(2026, 4, activity_id=activity.id)
        self.assertEqual(len(april), 2)
        self.assertTrue(all(row.display_status == DISPLAY_TO_PLAN for row in april))
        self.assertFalse(
            yearly_plan_service.is_month_automatically_processed(2026, 4, today=date(2026, 6, 1))
        )
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=3,
            reason="Přesunutý výskyt se nevykoná.",
        )
        april = self._rows(2026, 4, activity_id=activity.id)
        statuses = sorted(row.display_status for row in april)
        self.assertEqual(statuses, [DISPLAY_TO_PLAN, DISPLAY_WILL_NOT_PERFORM])
        self.assertTrue(any(row.display_status == DISPLAY_TO_PLAN for row in april))
        skip_occurrence(
            activity.id,
            original_year=2026,
            original_month=4,
            reason="Ani pravidelný duben.",
        )
        april = self._rows(2026, 4, activity_id=activity.id)
        self.assertTrue(all(row.display_status == DISPLAY_WILL_NOT_PERFORM for row in april))
        anchor = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(anchor.calendar_start_month, 1)
        self.assertEqual(anchor.calendar_interval_months, 1)

    def test_history_stays_done_and_empty_month_is_processed(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="S provedením",
            next_due_date=date(2026, 2, 10),
            repeat_every=1,
            repeat_unit=UNIT_MONTHS,
            calendar_start_year=2026,
            calendar_start_month=2,
            calendar_interval_months=1,
        )
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 2, 12),
        )
        february = self._rows(2026, 2, activity_id=activity.id)
        self.assertEqual(len(february), 1)
        self.assertEqual(february[0].display_status, DISPLAY_DONE)
        self.assertEqual(
            yearly_plan_service.list_month_rows(2019, 3, today=date(2019, 3, 1)),
            [],
        )
        self.assertTrue(
            yearly_plan_service.is_month_automatically_processed(2019, 3, today=date(2019, 3, 1))
        )

    def test_stamp_does_not_override_dashboard_warning(self) -> None:
        item = yearly_plan_service.create(year=2026, month=8, title="Dashboard")
        today = date(2026, 8, 4)
        title = month_planning_attention_title(2026, 8)
        self.assertIn(title, [row.title for row in get_yearly_plan_month_reminder_items(today=today)])
        stamp = yearly_plan_service.mark_month_processed(
            2026,
            8,
            processed_at=datetime(2026, 8, 4, 8, 0),
        )
        self.assertEqual(stamp.month, 8)
        self.assertIn(title, [row.title for row in get_yearly_plan_month_reminder_items(today=today)])
        yearly_plan_service.skip_manual(item.id, reason="Už rozhodnuto.")
        self.assertNotIn(
            title,
            [row.title for row in get_yearly_plan_month_reminder_items(today=today)],
        )
        self.assertIsNotNone(yearly_plan_service.get_month_status(2026, 8))

        tab = YearlyPlanTab()
        try:
            tab.set_year_month(2026, 8)
            self.assertFalse(tab.mark_month_btn.isVisible())
            header = tab.table.header_text_for_month(8)
            self.assertIn("Zpracován", header)
            self.assertNotIn("4. 8. 2026", header)
        finally:
            tab.deleteLater()
            self.app.processEvents()
