"""AGENDA-ROCNI-2c: automatické splnění a resty Ročního plánu."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date, datetime, timedelta
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
        DISPLAY_CANCELLED,
        DISPLAY_DONE,
        DISPLAY_PLANNED,
        DISPLAY_REST,
        DISPLAY_VIA_MEETING,
        DISPLAY_VIA_TASK,
        SOURCE_MODULE_YEARLY_PLAN,
        STATUS_CANCELLED,
        status_label,
    )
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        month_has_ended,
        resolve_display_status,
        yearly_plan_service,
    )
    from moduly.schuzky.constants import (
        STATUS_CANCELLED as MEETING_CANCELLED,
    )
    from moduly.schuzky.constants import (
        STATUS_CLOSED as MEETING_CLOSED,
    )
    from moduly.schuzky.constants import (
        STATUS_HELD as MEETING_HELD,
    )
    from moduly.schuzky.constants import (
        STATUS_PLANNED as MEETING_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaRocni2cTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for year in (2025, 2026, 2027):
            for item in list(yearly_plan_service.list_for_year(year)):
                if item.status != STATUS_CANCELLED:
                    yearly_plan_service.cancel(item.id)

    def _create_item(self, *, year: int, month: int, title: str):
        return yearly_plan_service.create(year=year, month=month, title=title)

    def _link_task(self, item, *, completed: bool = False, requires_verification: bool = False):
        task = task_service.create_task(
            title=item.title,
            due_date=date(item.year, item.month, 15),
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=item.id,
            requires_verification=requires_verification,
            completed=completed,
            completed_date=date(item.year, item.month, 20) if completed else None,
        )
        return yearly_plan_service.link_task(item.id, task.id), task

    def _link_meeting(self, item, *, status: str):
        starts = datetime(item.year, item.month, 10, 10, 0, 0)
        meeting = meeting_service.create_meeting(
            title=item.title,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            status=status,
        )
        return yearly_plan_service.link_meeting(item.id, meeting.id), meeting

    def test_completed_task_is_done(self) -> None:
        item = self._create_item(year=2026, month=5, title="Úkol hotový")
        linked, task = self._link_task(item, completed=True)
        self.assertEqual(task.computed_status, "Ukončeno")
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 5, 15)),
            DISPLAY_DONE,
        )
        self.assertEqual(status_label(DISPLAY_DONE), "Splněno")
        # stored status remains via_task
        self.assertEqual(yearly_plan_service.get_by_id(item.id).status, "via_task")

    def test_open_task_is_via_task(self) -> None:
        item = self._create_item(year=2026, month=5, title="Úkol otevřený")
        linked, task = self._link_task(item, completed=False)
        self.assertEqual(task.computed_status, "Aktivní")
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 5, 15)),
            DISPLAY_VIA_TASK,
        )

    def test_closed_meeting_is_done(self) -> None:
        item = self._create_item(year=2026, month=6, title="Událost uzavřená")
        linked, _meeting = self._link_meeting(item, status=MEETING_CLOSED)
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 6, 15)),
            DISPLAY_DONE,
        )

    def test_held_meeting_is_via_meeting(self) -> None:
        item = self._create_item(year=2026, month=6, title="Událost proběhla")
        linked, _meeting = self._link_meeting(item, status=MEETING_HELD)
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 6, 15)),
            DISPLAY_VIA_MEETING,
        )
        planned_item = self._create_item(year=2026, month=6, title="Událost naplánovaná")
        planned_linked, _ = self._link_meeting(planned_item, status=MEETING_PLANNED)
        self.assertEqual(
            resolve_display_status(planned_linked, today=date(2026, 6, 15)),
            DISPLAY_VIA_MEETING,
        )

    def test_cancelled_meeting_is_not_done(self) -> None:
        item = self._create_item(year=2026, month=6, title="Událost zrušená")
        linked, _meeting = self._link_meeting(item, status=MEETING_CANCELLED)
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 6, 15)),
            DISPLAY_PLANNED,
        )
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 7, 1)),
            DISPLAY_REST,
        )

    def test_cancelled_item_never_rest(self) -> None:
        item = self._create_item(year=2026, month=3, title="Zrušená položka")
        cancelled = yearly_plan_service.cancel(item.id)
        self.assertEqual(
            resolve_display_status(cancelled, today=date(2026, 10, 1)),
            DISPLAY_CANCELLED,
        )
        self.assertNotEqual(
            resolve_display_status(cancelled, today=date(2026, 10, 1)),
            DISPLAY_REST,
        )
        self.assertEqual(status_label(DISPLAY_CANCELLED), "Zrušeno")

    def test_past_unfinished_is_rest(self) -> None:
        item = self._create_item(year=2026, month=9, title="Září rest")
        self.assertTrue(month_has_ended(2026, 9, today=date(2026, 10, 1)))
        self.assertEqual(
            resolve_display_status(item, today=date(2026, 10, 1)),
            DISPLAY_REST,
        )
        linked, _ = self._link_task(item, completed=False)
        self.assertEqual(
            resolve_display_status(linked, today=date(2026, 10, 1)),
            DISPLAY_REST,
        )

    def test_current_and_future_month_not_rest(self) -> None:
        current = self._create_item(year=2026, month=10, title="Aktuální")
        future = self._create_item(year=2026, month=12, title="Budoucí")
        today = date(2026, 10, 15)
        self.assertFalse(month_has_ended(2026, 10, today=today))
        self.assertEqual(resolve_display_status(current, today=today), DISPLAY_PLANNED)
        self.assertEqual(resolve_display_status(future, today=today), DISPLAY_PLANNED)

    def test_moved_item_evaluated_by_new_month(self) -> None:
        item = self._create_item(year=2026, month=8, title="Přesun")
        # bez přesunu by v říjnu byl rest
        self.assertEqual(
            resolve_display_status(item, today=date(2026, 10, 1)),
            DISPLAY_REST,
        )
        moved = yearly_plan_service.move_to_month(item.id, to_year=2026, to_month=11)
        self.assertEqual(moved.month, 11)
        self.assertEqual(
            resolve_display_status(moved, today=date(2026, 10, 1)),
            DISPLAY_PLANNED,
        )

    def test_month_summary_matches_display_statuses(self) -> None:
        today = date(2026, 10, 1)
        done_item = self._create_item(year=2026, month=9, title="S1")
        self._link_task(done_item, completed=True)
        open_task = self._create_item(year=2026, month=9, title="S2")
        self._link_task(open_task, completed=False)
        held = self._create_item(year=2026, month=9, title="S3")
        self._link_meeting(held, status=MEETING_HELD)
        cancelled = yearly_plan_service.cancel(
            self._create_item(year=2026, month=9, title="S4").id
        )
        plain_rest = self._create_item(year=2026, month=9, title="S5")

        items = yearly_plan_service.list_for_month(2026, 9)
        # include only our titles from this test (cancelled leftovers may exist)
        titles = {"S1", "S2", "S3", "S4", "S5"}
        scoped = [item for item in items if item.title in titles]
        summary = yearly_plan_service.month_summary(scoped, today=today)

        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["done"], 1)
        self.assertEqual(summary["in_progress"], 0)  # past month → rest, not via_*
        self.assertEqual(summary["rest"], 3)  # open task, held meeting, plain
        self.assertEqual(summary["cancelled"], 1)

        # aktuální měsíc: řeší se se započítá
        now_item = self._create_item(year=2026, month=10, title="T1")
        self._link_task(now_item, completed=False)
        now_items = [
            item
            for item in yearly_plan_service.list_for_month(2026, 10)
            if item.title == "T1"
        ]
        now_summary = yearly_plan_service.month_summary(now_items, today=today)
        self.assertEqual(now_summary["in_progress"], 1)
        self.assertEqual(now_summary["rest"], 0)
        _ = cancelled  # keep cancel side-effect explicit


if __name__ == "__main__":
    unittest.main()
