"""AGENDA-ROCNI-2e: měsíční plánování z Ročního plánu."""

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

    from core.dashboard.attention_item import (
        ITEM_TYPE_YEARLY_PLAN_MONTH,
        SOURCE_LABEL_YEARLY_PLAN,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.shared.working_days import first_working_day, is_working_day
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.periodicke_cinnosti.constants import NEXT_FROM_PLANNED, UNIT_YEARS
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.rocni_plan.constants import (
        DISPLAY_REST,
        TAB_YEARLY_PLAN,
        month_planning_attention_title,
        month_planning_source_id,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        resolve_display_status,
        yearly_plan_service,
    )
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab


class AgendaRocni2eTestCase(unittest.TestCase):
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

    def _month_items(self, today: date):
        return [
            item
            for item in get_attention_items(today=today)
            if item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
        ]

    def test_first_working_day_weekday_month(self) -> None:
        # září 2026 začíná v úterý
        self.assertEqual(first_working_day(2026, 9), date(2026, 9, 1))
        self.assertTrue(is_working_day(date(2026, 9, 1)))

    def test_first_working_day_weekend_start(self) -> None:
        # srpen 2026 začíná v sobotu → pondělí 3. 8.
        self.assertEqual(first_working_day(2026, 8), date(2026, 8, 3))
        # únor 2026 začíná v neděli → pondělí 2. 2.
        self.assertEqual(first_working_day(2026, 2), date(2026, 2, 2))

    def test_attention_before_first_working_day(self) -> None:
        items = self._month_items(date(2026, 8, 2))  # neděle před Po 3. 8.
        self.assertEqual(items, [])
        self.assertFalse(
            yearly_plan_service.should_show_month_planning_attention(
                today=date(2026, 8, 2)
            )
        )

    def test_attention_from_first_working_day(self) -> None:
        today = date(2026, 8, 3)
        items = self._month_items(today)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(
            item.title,
            month_planning_attention_title(2026, 8),
        )
        self.assertEqual(item.title, "Zpracovat úkoly měsíce – srpen 2026")
        self.assertEqual(item.subtitle, SOURCE_LABEL_YEARLY_PLAN)
        self.assertEqual(item.source_id, month_planning_source_id(2026, 8))
        self.assertEqual(item.date, date(2026, 8, 3))
        self.assertEqual(item.open_metadata.get("year"), 2026)
        self.assertEqual(item.open_metadata.get("month"), 8)

    def test_open_leads_to_yearly_plan_month(self) -> None:
        page = AgendaPage()
        page.open_yearly_plan(2026, 9)
        index = page.tabs.indexOf(page.yearly_plan_tab)
        self.assertEqual(page.tabs.currentIndex(), index)
        self.assertEqual(page.tabs.tabText(index), TAB_YEARLY_PLAN)
        self.assertEqual(page.yearly_plan_tab.current_year(), 2026)
        self.assertEqual(page.yearly_plan_tab.current_month(), 9)
        page.close()

    def test_mark_month_processed_hides_attention(self) -> None:
        today = date(2026, 9, 7)
        self.assertEqual(len(self._month_items(today)), 1)
        status = yearly_plan_service.mark_month_processed(
            2026,
            9,
            processed_at=datetime(2026, 9, 7, 10, 0, 0),
        )
        self.assertEqual(status.year, 2026)
        self.assertEqual(status.month, 9)
        self.assertEqual(len(self._month_items(today)), 0)
        self.assertTrue(yearly_plan_service.is_month_processed(2026, 9))

        tab = YearlyPlanTab()
        tab.set_year_month(2026, 9)
        header = tab.table.header_text_for_month(9)
        self.assertIn("Zpracováno:", header)
        self.assertIn("7. 9. 2026", header)
        self.assertIn("Září", header)
        tab.close()

    def test_mark_month_does_not_change_item_statuses(self) -> None:
        item = yearly_plan_service.create(
            year=2030,
            month=5,
            title="Rest zůstává",
        )
        before = resolve_display_status(item, today=date(2030, 6, 1))
        self.assertEqual(before, DISPLAY_REST)
        yearly_plan_service.mark_month_processed(2030, 5)
        reloaded = yearly_plan_service.get_by_id(item.id)
        after = resolve_display_status(reloaded, today=date(2030, 6, 1))
        self.assertEqual(after, DISPLAY_REST)
        self.assertEqual(reloaded.status, item.status)

    def test_new_manual_item_after_processed_does_not_restore_attention(self) -> None:
        today = date(2030, 10, 5)
        yearly_plan_service.mark_month_processed(2030, 10)
        self.assertEqual(self._month_items(today), [])
        yearly_plan_service.create(year=2030, month=10, title="Dodatečná položka")
        self.assertEqual(self._month_items(today), [])
        self.assertTrue(yearly_plan_service.is_month_processed(2030, 10))

    def test_new_periodic_after_processed_does_not_restore_attention(self) -> None:
        today = date(2030, 11, 10)
        yearly_plan_service.mark_month_processed(2030, 11)
        self.assertEqual(self._month_items(today), [])
        periodic_activity_service.create_activity(
            title="Nová periodika po zpracování",
            next_due_date=date(2030, 11, 15),
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            next_from=NEXT_FROM_PLANNED,
            active=True,
        )
        self.assertEqual(self._month_items(today), [])
        rows = yearly_plan_service.list_month_rows(2030, 11, today=today)
        self.assertTrue(any(row.is_periodic for row in rows))
        self.assertTrue(yearly_plan_service.is_month_processed(2030, 11))


if __name__ == "__main__":
    unittest.main()
