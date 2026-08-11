"""AGENDA-ANNUAL-PLAN-REMINDER-1: měsíční plán v Připomínkách."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
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

    from core.dashboard.attention_item import ITEM_TYPE_YEARLY_PLAN_MONTH
    from core.dashboard.attention_service import (
        get_attention_items,
        get_yearly_plan_month_reminder_items,
    )
    from core.dashboard.widget_today import TodayWidget
    from core.shared.working_days import first_working_day
    from moduly.rocni_plan.constants import month_planning_attention_title
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service


class AgendaAnnualPlanReminder1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for year in range(2025, 2032):
            for month in range(1, 13):
                yearly_plan_service.month_status_repository.delete_for_month(
                    year, month
                )
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != "cancelled":
                    yearly_plan_service.cancel(item.id)
        from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
            periodic_activity_service,
        )

        for activity in list(periodic_activity_service.get_all()):
            if activity.active:
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
                )

    def _titles(self, today: date) -> list[str]:
        return [item.title for item in get_yearly_plan_month_reminder_items(today=today)]

    def test_before_first_working_day_hidden(self) -> None:
        # srpen 2026: 1.–2. víkend, první pracovní den 3. 8.
        self.assertEqual(first_working_day(2026, 8), date(2026, 8, 3))
        self.assertEqual(self._titles(date(2026, 8, 2)), [])
        widget = TodayWidget()
        widget.refresh(today=date(2026, 8, 2))
        self.assertNotIn("Zpracovat úkoly měsíce – srpen 2026", widget.content.text())
        widget.close()

    def test_on_first_working_day_in_reminders_and_upcoming(self) -> None:
        today = date(2026, 8, 3)
        title = month_planning_attention_title(2026, 8)
        items = get_yearly_plan_month_reminder_items(today=today)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, title)
        self.assertEqual(items[0].item_type, ITEM_TYPE_YEARLY_PLAN_MONTH)

        upcoming = get_attention_items(today=today)
        self.assertTrue(
            any(item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH for item in upcoming)
        )

        widget = TodayWidget()
        widget.refresh(today=today)
        text = widget.content.text()
        self.assertIn(title, text)
        self.assertIn("🔵", text)
        self.assertIn("03.08.2026", text)
        widget.close()

    def test_stays_after_first_working_day(self) -> None:
        today = date(2026, 8, 9)
        title = month_planning_attention_title(2026, 8)
        self.assertIn(title, self._titles(today))
        widget = TodayWidget()
        widget.refresh(today=today)
        text = widget.content.text()
        self.assertIn(title, text)
        self.assertIn("🔴", text)
        widget.close()

    def test_mark_processed_removes(self) -> None:
        today = date(2026, 8, 9)
        yearly_plan_service.mark_month_processed(
            2026, 8, processed_at=datetime(2026, 8, 9, 10, 0, 0)
        )
        self.assertEqual(self._titles(today), [])
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
                for item in get_attention_items(today=today)
            )
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertNotIn("Zpracovat úkoly měsíce – srpen 2026", widget.content.text())
        widget.close()

    def test_empty_month_still_reminded(self) -> None:
        # Září 2026 bez položek — první pracovní den 1. 9.
        today = date(2026, 9, 1)
        self.assertEqual(yearly_plan_service.list_month_rows(2026, 9, today=today), [])
        title = month_planning_attention_title(2026, 9)
        self.assertIn(title, self._titles(today))

    def test_previous_month_not_carried(self) -> None:
        # Srpen nezpracován, jsme v září — jen září.
        today = date(2026, 9, 1)
        titles = self._titles(today)
        self.assertIn(month_planning_attention_title(2026, 9), titles)
        self.assertNotIn(month_planning_attention_title(2026, 8), titles)
        self.assertEqual(len(titles), 1)

    def test_plan_items_not_reminded_individually(self) -> None:
        yearly_plan_service.create(year=2026, month=9, title="Ruční položka plánu")
        today = date(2026, 9, 5)
        items = get_yearly_plan_month_reminder_items(today=today)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, month_planning_attention_title(2026, 9))
        self.assertNotIn("Ruční položka plánu", items[0].title)
        upcoming = get_attention_items(today=today)
        self.assertFalse(any("Ruční položka plánu" in (item.title or "") for item in upcoming))


if __name__ == "__main__":
    unittest.main()
