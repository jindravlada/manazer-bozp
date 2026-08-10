"""AGENDA-ROCNI-2a: datový základ Ročního plánu."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.rocni_plan.constants import (
        STATUS_CANCELLED,
        STATUS_PLANNED,
        STATUS_VIA_MEETING,
        STATUS_VIA_TASK,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        YearlyPlanValidationError,
        yearly_plan_service,
    )


class AgendaRocni2aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for item in list(yearly_plan_service.list_for_year(2026)):
            yearly_plan_service.cancel(item.id)
        for item in list(yearly_plan_service.list_for_year(2027)):
            yearly_plan_service.cancel(item.id)

    def test_create_and_update(self) -> None:
        created = yearly_plan_service.create(
            year=2026,
            month=9,
            title="Aktualizovat dokumentaci",
            note="BOZP směrnice",
        )
        self.assertIsNotNone(created.id)
        self.assertEqual(created.year, 2026)
        self.assertEqual(created.month, 9)
        self.assertEqual(created.title, "Aktualizovat dokumentaci")
        self.assertEqual(created.status, STATUS_PLANNED)
        self.assertIsNone(created.task_id)
        self.assertIsNone(created.meeting_id)

        updated = yearly_plan_service.update(
            created.id,
            year=2026,
            month=9,
            title="Aktualizovat dokumentaci – upraveno",
            note="Poznámka 2",
            status=STATUS_PLANNED,
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.title, "Aktualizovat dokumentaci – upraveno")
        self.assertEqual(updated.note, "Poznámka 2")

        month_items = yearly_plan_service.list_for_month(2026, 9)
        self.assertTrue(any(item.id == created.id for item in month_items))
        year_items = yearly_plan_service.list_for_year(2026)
        self.assertTrue(any(item.id == created.id for item in year_items))

    def test_cancel(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=3,
            title="Kontrola skladu",
        )
        cancelled = yearly_plan_service.cancel(item.id)
        self.assertEqual(cancelled.id, item.id)
        self.assertEqual(cancelled.status, STATUS_CANCELLED)

    def test_move_within_year_keeps_id(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=5,
            title="Připravit školení",
        )
        original_id = item.id
        moved = yearly_plan_service.move_to_month(item.id, to_year=2026, to_month=8)
        self.assertEqual(moved.id, original_id)
        self.assertEqual(moved.year, 2026)
        self.assertEqual(moved.month, 8)
        self.assertEqual(moved.status, STATUS_PLANNED)
        may_ids = [row.id for row in yearly_plan_service.list_for_month(2026, 5)]
        self.assertNotIn(original_id, may_ids)
        self.assertIn(
            original_id,
            [row.id for row in yearly_plan_service.list_for_month(2026, 8)],
        )

    def test_move_december_to_january_next_year(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=12,
            title="Roční shrnutí",
        )
        original_id = item.id
        moved = yearly_plan_service.move_to_month(item.id, to_year=2027, to_month=1)
        self.assertEqual(moved.id, original_id)
        self.assertEqual(moved.year, 2027)
        self.assertEqual(moved.month, 1)
        history = yearly_plan_service.get_move_history(original_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].from_year, 2026)
        self.assertEqual(history[0].from_month, 12)
        self.assertEqual(history[0].to_year, 2027)
        self.assertEqual(history[0].to_month, 1)

    def test_multiple_moves_history(self) -> None:
        item = yearly_plan_service.create(
            year=2026,
            month=1,
            title="Více přesunů",
        )
        item_id = item.id
        yearly_plan_service.move_to_month(item_id, to_year=2026, to_month=4)
        yearly_plan_service.move_to_month(item_id, to_year=2026, to_month=7)
        yearly_plan_service.move_to_month(item_id, to_year=2026, to_month=10)

        history = yearly_plan_service.get_move_history(item_id)
        self.assertEqual(len(history), 3)
        self.assertEqual(
            [(m.from_month, m.to_month) for m in history],
            [(1, 4), (4, 7), (7, 10)],
        )
        reloaded = yearly_plan_service.get_by_id(item_id)
        self.assertEqual(reloaded.month, 10)
        self.assertEqual(reloaded.id, item_id)

    def test_month_validation(self) -> None:
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.create(year=2026, month=0, title="X")
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.create(year=2026, month=13, title="X")
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.create(year=1899, month=6, title="X")
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.create(year=2026, month=6, title="   ")

    def test_reject_both_task_and_meeting(self) -> None:
        with self.assertRaises(YearlyPlanValidationError) as ctx:
            yearly_plan_service.create(
                year=2026,
                month=6,
                title="Konflikt vazeb",
                task_id=1,
                meeting_id=2,
            )
        self.assertIn("Úkol", str(ctx.exception))
        self.assertIn("Událost", str(ctx.exception))

        item = yearly_plan_service.create(
            year=2026,
            month=6,
            title="Jen úkol",
            status=STATUS_VIA_TASK,
            task_id=10,
        )
        with self.assertRaises(YearlyPlanValidationError):
            yearly_plan_service.update(
                item.id,
                year=2026,
                month=6,
                title="Jen úkol",
                status=STATUS_VIA_MEETING,
                task_id=10,
                meeting_id=20,
            )


if __name__ == "__main__":
    unittest.main()
