"""AGENDA-ROCNI-2d: periodické činnosti v Ročním plánu."""

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

    from moduly.periodicke_cinnosti.constants import (
        NEXT_FROM_PLANNED,
        UNIT_MONTHS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        periodic_activity_service,
    )
    from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import (
        PeriodicActivityDialog,
    )
    from moduly.rocni_plan.constants import (
        COL_SOURCE,
        COL_TITLE,
        DISPLAY_DONE,
        DISPLAY_PLANNED,
        DISPLAY_REST,
        ROW_KIND_MANUAL,
        ROW_KIND_PERIODIC,
        SOURCE_LABEL_MANUAL,
        SOURCE_LABEL_PERIODIC,
        STATUS_CANCELLED,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        list_periodic_rows_for_month,
        yearly_plan_service,
    )
    from moduly.rocni_plan.ui.yearly_plan_tab import YearlyPlanTab


class AgendaRocni2dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for year in (2025, 2026, 2027):
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != STATUS_CANCELLED:
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

    def _create_periodic(
        self,
        *,
        title: str,
        due: date,
        every: int = 1,
        unit: str = UNIT_MONTHS,
        active: bool = True,
    ):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=due,
            repeat_every=every,
            repeat_unit=unit,
            next_from=NEXT_FROM_PLANNED,
            active=active,
        )

    def test_active_periodic_in_month(self) -> None:
        activity = self._create_periodic(
            title="Revize hasicích přístrojů",
            due=date(2026, 5, 12),
        )
        rows = yearly_plan_service.list_month_rows(
            2026, 5, today=date(2026, 5, 1)
        )
        periodic = [row for row in rows if row.is_periodic]
        self.assertEqual(len(periodic), 1)
        self.assertEqual(periodic[0].activity_id, activity.id)
        self.assertEqual(periodic[0].display_status, DISPLAY_PLANNED)
        self.assertEqual(periodic[0].source_label, SOURCE_LABEL_PERIODIC)
        self.assertEqual(periodic[0].planned_due_date, date(2026, 5, 12))

        manual = yearly_plan_service.create(
            year=2026, month=5, title="Ruční položka"
        )
        mixed = yearly_plan_service.list_month_rows(
            2026, 5, today=date(2026, 5, 1)
        )
        kinds = {row.kind for row in mixed}
        self.assertEqual(kinds, {ROW_KIND_MANUAL, ROW_KIND_PERIODIC})
        self.assertEqual(
            sum(1 for row in mixed if row.plan_item_id == manual.id), 1
        )

    def test_inactive_not_shown(self) -> None:
        self._create_periodic(
            title="Neaktivní kontrola",
            due=date(2026, 5, 10),
            active=False,
        )
        rows = list_periodic_rows_for_month(2026, 5, today=date(2026, 5, 1))
        self.assertEqual(rows, [])

    def test_future_cycles_projected(self) -> None:
        activity = self._create_periodic(
            title="Roční školení",
            due=date(2026, 3, 1),
            every=1,
            unit=UNIT_YEARS,
        )
        march_2026 = yearly_plan_service.list_month_rows(
            2026, 3, today=date(2026, 1, 15)
        )
        march_2027 = yearly_plan_service.list_month_rows(
            2027, 3, today=date(2026, 1, 15)
        )
        self.assertEqual(
            [row.planned_due_date for row in march_2026 if row.is_periodic],
            [date(2026, 3, 1)],
        )
        self.assertEqual(
            [row.planned_due_date for row in march_2027 if row.is_periodic],
            [date(2027, 3, 1)],
        )
        self.assertEqual(march_2027[0].activity_id, activity.id)

        monthly = self._create_periodic(
            title="Měsíční obchůzka",
            due=date(2026, 1, 5),
            every=1,
            unit=UNIT_MONTHS,
        )
        june = [
            row
            for row in yearly_plan_service.list_month_rows(
                2026, 6, today=date(2026, 1, 15)
            )
            if row.activity_id == monthly.id
        ]
        self.assertEqual(len(june), 1)
        self.assertEqual(june[0].planned_due_date, date(2026, 6, 5))

    def test_completed_stays_in_original_month(self) -> None:
        activity = self._create_periodic(
            title="Provedená kontrola",
            due=date(2026, 2, 10),
            every=1,
            unit=UNIT_MONTHS,
        )
        occurrence = periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 2, 12),
        )
        self.assertEqual(occurrence.planned_due_date, date(2026, 2, 10))
        reloaded = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(reloaded.next_due_date, date(2026, 3, 10))

        february = yearly_plan_service.list_month_rows(
            2026, 2, today=date(2026, 4, 1)
        )
        feb_rows = [row for row in february if row.activity_id == activity.id]
        self.assertEqual(len(feb_rows), 1)
        self.assertEqual(feb_rows[0].display_status, DISPLAY_DONE)
        self.assertEqual(feb_rows[0].planned_due_date, date(2026, 2, 10))
        self.assertEqual(feb_rows[0].occurrence_id, occurrence.id)

        march = [
            row
            for row in yearly_plan_service.list_month_rows(
                2026, 3, today=date(2026, 4, 1)
            )
            if row.activity_id == activity.id
        ]
        self.assertEqual(len(march), 1)
        self.assertEqual(march[0].display_status, DISPLAY_REST)
        self.assertEqual(march[0].planned_due_date, date(2026, 3, 10))

    def test_overdue_without_occurrence_is_rest(self) -> None:
        activity = self._create_periodic(
            title="Zmeškaná perioda",
            due=date(2026, 1, 20),
        )
        rows = [
            row
            for row in yearly_plan_service.list_month_rows(
                2026, 1, today=date(2026, 2, 5)
            )
            if row.activity_id == activity.id
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].display_status, DISPLAY_REST)

    def test_no_duplicates(self) -> None:
        activity = self._create_periodic(
            title="Bez duplicit",
            due=date(2026, 4, 8),
            every=1,
            unit=UNIT_MONTHS,
        )
        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 4, 9),
        )
        april = [
            row
            for row in yearly_plan_service.list_month_rows(
                2026, 4, today=date(2026, 5, 1)
            )
            if row.activity_id == activity.id
        ]
        self.assertEqual(len(april), 1)
        self.assertEqual(april[0].display_status, DISPLAY_DONE)

        keys = [
            (row.activity_id, row.planned_due_date)
            for row in yearly_plan_service.list_month_rows(
                2026, 5, today=date(2026, 5, 1)
            )
            if row.is_periodic
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_not_copied_into_yearly_plan_items(self) -> None:
        self._create_periodic(title="Jen projekce", due=date(2026, 8, 1))
        active = [
            item
            for item in yearly_plan_service.list_for_month(2026, 8)
            if item.status != STATUS_CANCELLED
        ]
        self.assertEqual(active, [])
        rows = yearly_plan_service.list_month_rows(2026, 8, today=date(2026, 8, 1))
        self.assertTrue(any(row.is_periodic for row in rows))

    def test_double_click_opens_periodic_and_actions_disabled(self) -> None:
        activity = self._create_periodic(
            title="Otevřít dialog",
            due=date(2026, 9, 15),
        )
        yearly_plan_service.create(year=2026, month=9, title="Ruční")
        tab = YearlyPlanTab()
        tab.set_year_month(2026, 9)

        periodic_row = None
        for row in range(tab.table.rowCount()):
            if tab.table.item(row, COL_SOURCE).text() == SOURCE_LABEL_PERIODIC:
                periodic_row = row
                break
        self.assertIsNotNone(periodic_row)
        tab.table.selectRow(periodic_row)
        tab._refresh_action_buttons()
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.create_task_btn.isEnabled())
        self.assertFalse(tab.create_meeting_btn.isEnabled())
        self.assertFalse(tab.move_btn.isEnabled())
        self.assertFalse(tab.cancel_btn.isEnabled())
        self.assertEqual(tab.table.selected_activity_id(), activity.id)

        opened = []

        class _CaptureDialog(PeriodicActivityDialog):
            def __init__(self, *args, **kwargs):
                opened.append(kwargs.get("activity") or (args[1] if len(args) > 1 else None))
                super().__init__(*args, **kwargs)

        with patch(
            "moduly.rocni_plan.ui.yearly_plan_tab.PeriodicActivityDialog",
            _CaptureDialog,
        ), patch(
            "moduly.rocni_plan.ui.yearly_plan_tab.exec_maximized",
            return_value=0,
        ):
            tab.edit_selected()
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].id, activity.id)

        manual_row = None
        for row in range(tab.table.rowCount()):
            source_item = tab.table.item(row, COL_SOURCE)
            title_item = tab.table.item(row, COL_TITLE)
            if (
                source_item is not None
                and source_item.text() == SOURCE_LABEL_MANUAL
                and title_item is not None
                and title_item.text() == "Ruční"
            ):
                manual_row = row
                break
        self.assertIsNotNone(manual_row)
        tab.table.selectRow(manual_row)
        tab._refresh_action_buttons()
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.move_btn.isEnabled())
        tab.close()

    def test_month_summary_includes_periodics(self) -> None:
        yearly_plan_service.create(year=2026, month=10, title="Ruční plán")
        self._create_periodic(title="Periodika OK", due=date(2026, 10, 5))
        overdue = self._create_periodic(
            title="Periodika rest",
            due=date(2026, 9, 5),
            every=1,
            unit=UNIT_YEARS,
        )
        done = self._create_periodic(
            title="Periodika hotovo",
            due=date(2026, 10, 20),
            every=1,
            unit=UNIT_YEARS,
        )
        periodic_activity_service.record_performance(
            done.id,
            performed_at=date(2026, 10, 21),
        )

        october = yearly_plan_service.list_month_rows(
            2026, 10, today=date(2026, 10, 15)
        )
        summary = yearly_plan_service.month_summary(
            october, today=date(2026, 10, 15)
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["done"], 1)
        self.assertEqual(summary["planned"], 2)
        self.assertEqual(summary["rest"], 0)

        september = yearly_plan_service.list_month_rows(
            2026, 9, today=date(2026, 10, 15)
        )
        sep_summary = yearly_plan_service.month_summary(
            september, today=date(2026, 10, 15)
        )
        self.assertGreaterEqual(sep_summary["rest"], 1)
        self.assertTrue(
            any(
                row.activity_id == overdue.id and row.display_status == DISPLAY_REST
                for row in september
            )
        )

        tab = YearlyPlanTab()
        tab.set_year_month(2026, 10)
        text = tab.table.header_text_for_month(10)
        self.assertIn("Celkem: 3", text)
        self.assertIn("Splněno: 1", text)
        # Kompatibilní souhrn fokusovaného měsíce.
        self.assertIn("Celkem: 3", tab.summary_label.text())
        tab.close()


if __name__ == "__main__":
    unittest.main()
