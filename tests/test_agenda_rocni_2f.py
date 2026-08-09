"""AGENDA-ROCNI-2f: opakování ručních položek Ročního plánu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
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

    from core.shared.working_days import first_working_day
    from moduly.rocni_plan.constants import (
        DISPLAY_CANCELLED,
        DISPLAY_VIA_MEETING,
        DISPLAY_VIA_TASK,
        DUE_KIND_DAY,
        DUE_KIND_FIRST_WORKING_DAY,
        DUE_KIND_NONE,
        REPEAT_UNIT_MONTHS,
        REPEAT_UNIT_YEARS,
        SOURCE_MODULE_YEARLY_PLAN,
        STATUS_CANCELLED,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        definition_occurs_in_month,
        is_repeating,
        resolve_planned_due_date,
        yearly_plan_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaRocni2fTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from moduly.rocni_plan.constants import REPEAT_UNIT_NONE

        for item in list(yearly_plan_service.repository.list_repeating()):
            yearly_plan_service.update(
                item.id,
                year=item.year,
                month=item.month,
                title=f"OLD-{item.id}-{item.title}",
                note=item.note or "",
                status=item.status or "planned",
                task_id=None,
                meeting_id=None,
                repeat_every=0,
                repeat_unit=REPEAT_UNIT_NONE,
                due_kind=DUE_KIND_NONE,
                due_day=None,
            )
        for year in (2040, 2041, 2045, 2046):
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != STATUS_CANCELLED and not is_repeating(item):
                    yearly_plan_service.cancel(item.id)

    def _create_repeating(self, **kwargs):
        defaults = dict(
            year=2040,
            month=1,
            title="Vstupní školení",
            repeat_every=1,
            repeat_unit=REPEAT_UNIT_MONTHS,
            due_kind=DUE_KIND_FIRST_WORKING_DAY,
        )
        defaults.update(kwargs)
        return yearly_plan_service.create(**defaults)

    def test_monthly_repeat(self) -> None:
        item = self._create_repeating(title="Měsíční")
        for month in (1, 2, 3, 12):
            self.assertTrue(definition_occurs_in_month(item, 2040, month))
            rows = yearly_plan_service.list_month_rows(2040, month, today=date(2040, 1, 15))
            self.assertEqual(
                sum(1 for row in rows if row.plan_item_id == item.id),
                1,
            )
        self.assertFalse(definition_occurs_in_month(item, 2039, 12))

    def test_every_three_months(self) -> None:
        item = self._create_repeating(
            title="Čtvrtletní",
            repeat_every=3,
            due_kind=DUE_KIND_NONE,
        )
        for month, expected in (
            (1, True),
            (2, False),
            (4, True),
            (7, True),
            (10, True),
            (11, False),
        ):
            self.assertEqual(
                definition_occurs_in_month(item, 2040, month),
                expected,
                msg=f"month={month}",
            )

    def test_yearly_repeat(self) -> None:
        item = self._create_repeating(
            title="Roční",
            month=3,
            repeat_every=1,
            repeat_unit=REPEAT_UNIT_YEARS,
            due_kind=DUE_KIND_DAY,
            due_day=15,
        )
        self.assertTrue(definition_occurs_in_month(item, 2040, 3))
        self.assertTrue(definition_occurs_in_month(item, 2041, 3))
        self.assertFalse(definition_occurs_in_month(item, 2040, 4))
        self.assertEqual(
            resolve_planned_due_date(item, 2041, 3),
            date(2041, 3, 15),
        )

    def test_every_five_years(self) -> None:
        item = self._create_repeating(
            title="Pětiletá",
            year=2040,
            month=6,
            repeat_every=5,
            repeat_unit=REPEAT_UNIT_YEARS,
        )
        self.assertTrue(definition_occurs_in_month(item, 2040, 6))
        self.assertFalse(definition_occurs_in_month(item, 2041, 6))
        self.assertTrue(definition_occurs_in_month(item, 2045, 6))
        rows = yearly_plan_service.list_month_rows(2045, 6, today=date(2045, 1, 1))
        self.assertEqual(
            sum(1 for row in rows if row.plan_item_id == item.id),
            1,
        )

    def test_first_working_day(self) -> None:
        item = self._create_repeating(
            month=8,
            due_kind=DUE_KIND_FIRST_WORKING_DAY,
        )
        due = resolve_planned_due_date(item, 2040, 8)
        self.assertEqual(due, first_working_day(2040, 8))
        # srpen 2040 začíná ve středu
        self.assertEqual(due, date(2040, 8, 1))

    def test_specific_day(self) -> None:
        item = self._create_repeating(
            due_kind=DUE_KIND_DAY,
            due_day=31,
        )
        self.assertEqual(resolve_planned_due_date(item, 2040, 2), date(2040, 2, 29))
        self.assertEqual(resolve_planned_due_date(item, 2040, 1), date(2040, 1, 31))

    def test_cancel_one_occurrence_keeps_others(self) -> None:
        item = self._create_repeating(title="Zrušení výskytu")
        yearly_plan_service.cancel_occurrence(item.id, year=2040, month=3)
        march = yearly_plan_service.list_month_rows(2040, 3, today=date(2040, 3, 1))
        april = yearly_plan_service.list_month_rows(2040, 4, today=date(2040, 3, 1))
        march_row = next(row for row in march if row.plan_item_id == item.id)
        april_row = next(row for row in april if row.plan_item_id == item.id)
        self.assertEqual(march_row.display_status, DISPLAY_CANCELLED)
        self.assertNotEqual(april_row.display_status, DISPLAY_CANCELLED)

    def test_move_one_occurrence_keeps_target_slot(self) -> None:
        item = self._create_repeating(title="Přesun výskytu")
        yearly_plan_service.move_occurrence(
            item.id,
            year=2040,
            month=9,
            to_year=2040,
            to_month=10,
        )
        september = [
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 9, today=date(2040, 9, 1)
            )
            if row.plan_item_id == item.id
        ]
        october = [
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 10, today=date(2040, 9, 1)
            )
            if row.plan_item_id == item.id
        ]
        self.assertEqual(september, [])
        self.assertEqual(len(october), 2)
        slots = {(row.slot_year, row.slot_month) for row in october}
        self.assertEqual(slots, {(2040, 9), (2040, 10)})

    def test_link_task_and_meeting_one_occurrence(self) -> None:
        item = self._create_repeating(title="Vazba výskytu")
        task = task_service.create_task(
            title=item.title,
            due_date=date(2040, 5, 10),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=item.id,
            requires_verification=False,
        )
        yearly_plan_service.link_task_occurrence(
            item.id,
            year=2040,
            month=5,
            task_id=task.id,
        )
        may = next(
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 5, today=date(2040, 5, 1)
            )
            if row.plan_item_id == item.id
        )
        june = next(
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 6, today=date(2040, 5, 1)
            )
            if row.plan_item_id == item.id
        )
        self.assertEqual(may.display_status, DISPLAY_VIA_TASK)
        self.assertEqual(may.link_text, f"Úkol #{task.id}")
        self.assertEqual(june.link_text, "—")

        starts = datetime(2040, 7, 10, 10, 0, 0)
        meeting = meeting_service.create_meeting(
            title=item.title,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
        )
        yearly_plan_service.link_meeting_occurrence(
            item.id,
            year=2040,
            month=7,
            meeting_id=meeting.id,
        )
        july = next(
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 7, today=date(2040, 5, 1)
            )
            if row.plan_item_id == item.id
        )
        self.assertEqual(july.display_status, DISPLAY_VIA_MEETING)
        self.assertEqual(july.link_text, f"Událost #{meeting.id}")
        may_again = next(
            row
            for row in yearly_plan_service.list_month_rows(
                2040, 5, today=date(2040, 5, 1)
            )
            if row.plan_item_id == item.id
        )
        self.assertEqual(may_again.link_text, f"Úkol #{task.id}")

    def test_not_copied_as_db_rows(self) -> None:
        item = self._create_repeating(title="Bez kopírování")
        may_items = yearly_plan_service.list_for_month(2040, 5)
        self.assertFalse(any(row.id == item.id for row in may_items))
        rows = yearly_plan_service.list_month_rows(2040, 5, today=date(2040, 5, 1))
        self.assertTrue(any(row.plan_item_id == item.id and row.is_recurring for row in rows))


if __name__ == "__main__":
    unittest.main()
