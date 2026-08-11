"""DASHBOARD-ATTENTION-UX-1: souběh Připomínek a Nadcházejících."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
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

    from core.dashboard.attention_item import (
        ITEM_TYPE_PERIODIC,
        ITEM_TYPE_YEARLY_PLAN_MONTH,
    )
    from core.dashboard.attention_service import (
        get_attention_items,
        get_periodic_reminder_items,
        get_yearly_plan_month_reminder_items,
    )
    from core.dashboard.widget_today import TodayWidget
    from moduly.periodicke_cinnosti.constants import NEXT_FROM_PLANNED, UNIT_DAYS, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.rocni_plan.constants import month_planning_attention_title
    from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service


class DashboardAttentionUx1TestCase(unittest.TestCase):
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
        for year in range(2025, 2032):
            for month in range(1, 13):
                yearly_plan_service.month_status_repository.delete_for_month(
                    year, month
                )

    def test_periodic_in_both_panels(self) -> None:
        activity = periodic_activity_service.create_activity(
            title="Periodika souběh",
            next_due_date=date(2026, 9, 30),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=14,
            notify_unit=UNIT_DAYS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        today = date(2026, 9, 16)
        self.assertTrue(
            any(item.source_id == activity.id for item in get_periodic_reminder_items(today=today))
        )
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_PERIODIC and item.source_id == activity.id
                for item in get_attention_items(today=today)
            )
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertIn("Periodika souběh", widget.content.text())
        widget.close()

    def test_month_plan_in_both_panels_on_first_working_day(self) -> None:
        today = date(2026, 8, 3)
        title = month_planning_attention_title(2026, 8)
        self.assertTrue(
            any(item.title == title for item in get_yearly_plan_month_reminder_items(today=today))
        )
        self.assertTrue(
            any(
                item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH and item.title == title
                for item in get_attention_items(today=today)
            )
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        self.assertIn(title, widget.content.text())
        widget.close()

    def test_reminders_do_not_exclude_from_upcoming(self) -> None:
        """Položka v Připomínkách není automaticky odfiltrována z Nadcházejících."""
        today = date(2026, 9, 1)
        reminder_ids = {
            (item.item_type, item.source_id)
            for item in get_yearly_plan_month_reminder_items(today=today)
        }
        self.assertTrue(reminder_ids)
        upcoming_ids = {
            (item.item_type, item.source_id)
            for item in get_attention_items(today=today)
        }
        self.assertTrue(reminder_ids.issubset(upcoming_ids))


if __name__ == "__main__":
    unittest.main()
