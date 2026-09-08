"""AGENDA-SORT-FIX-1: výchozí řazení Termín → Priorita v Agendě i Nadcházejících."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.widget_upcoming_tasks import (
        COL_TYPE as UPCOMING_COL_TYPE,
        UpcomingTasksWidget,
    )
    from moduly.agenda.constants import (
        COL_TITLE,
        ITEM_TYPE_TASK,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_NORMAL,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaSortFix1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.commit()

    def _ordered_ids(self, wanted: set[int]) -> tuple[list[int], list[int]]:
        agenda_ids = [
            item.source_id
            for item in agenda_service.get_items(today=date(2026, 9, 8))
            if item.item_type == ITEM_TYPE_TASK and item.source_id in wanted
        ]
        page = AgendaPage()
        page.refresh()
        page_ids = []
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if (
                payload is not None
                and payload.item_type == ITEM_TYPE_TASK
                and payload.source_id in wanted
            ):
                page_ids.append(payload.source_id)

        widget = UpcomingTasksWidget()
        widget.refresh()
        upcoming_ids = []
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, UPCOMING_COL_TYPE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.item_type == ITEM_TYPE_TASK and payload.entity_id in wanted:
                upcoming_ids.append(payload.entity_id)
        widget.close()
        page.close()
        self.assertEqual(agenda_ids, page_ids)
        self.assertEqual(agenda_ids, upcoming_ids)
        return agenda_ids, upcoming_ids

    def test_earlier_due_before_later_regardless_of_priority(self) -> None:
        later_critical = task_service.create_task(
            title="Kritická 30.10.",
            due_date=date(2026, 10, 30),
            priority=PRIORITY_CRITICAL,
        )
        earlier_normal = task_service.create_task(
            title="Normální 10.09.",
            due_date=date(2026, 9, 10),
            priority=PRIORITY_NORMAL,
        )
        later_still_critical = task_service.create_task(
            title="Kritická 30.09.",
            due_date=date(2026, 9, 30),
            priority=PRIORITY_CRITICAL,
        )
        wanted = {later_critical.id, earlier_normal.id, later_still_critical.id}
        ordered, _ = self._ordered_ids(wanted)
        self.assertEqual(
            ordered,
            [earlier_normal.id, later_still_critical.id, later_critical.id],
        )

    def test_same_due_sorts_by_priority(self) -> None:
        due = date(2026, 9, 9)
        normal = task_service.create_task(
            title="Normální stejný den",
            due_date=due,
            priority=PRIORITY_NORMAL,
        )
        critical = task_service.create_task(
            title="Kritická stejný den",
            due_date=due,
            priority=PRIORITY_CRITICAL,
        )
        high = task_service.create_task(
            title="Vysoká stejný den",
            due_date=due,
            priority=PRIORITY_HIGH,
        )
        wanted = {normal.id, critical.id, high.id}
        ordered, _ = self._ordered_ids(wanted)
        self.assertEqual(ordered, [critical.id, high.id, normal.id])

    def test_missing_due_after_dated_then_by_priority(self) -> None:
        dated = task_service.create_task(
            title="S termínem nízká",
            due_date=date(2026, 9, 10),
            priority="Nízká",
        )
        no_due_normal = task_service.create_task(
            title="Bez termínu normální",
            priority=PRIORITY_NORMAL,
        )
        no_due_critical = task_service.create_task(
            title="Bez termínu kritická",
            priority=PRIORITY_CRITICAL,
        )
        wanted = {dated.id, no_due_normal.id, no_due_critical.id}
        ordered, _ = self._ordered_ids(wanted)
        self.assertEqual(ordered, [dated.id, no_due_critical.id, no_due_normal.id])

    def test_example_order_matches_spec(self) -> None:
        items = [
            task_service.create_task(
                title="09 kritická",
                due_date=date(2026, 9, 9),
                priority=PRIORITY_CRITICAL,
            ),
            task_service.create_task(
                title="09 vysoká",
                due_date=date(2026, 9, 9),
                priority=PRIORITY_HIGH,
            ),
            task_service.create_task(
                title="09 normální",
                due_date=date(2026, 9, 9),
                priority=PRIORITY_NORMAL,
            ),
            task_service.create_task(
                title="10 kritická",
                due_date=date(2026, 9, 10),
                priority=PRIORITY_CRITICAL,
            ),
            task_service.create_task(
                title="30.09 kritická",
                due_date=date(2026, 9, 30),
                priority=PRIORITY_CRITICAL,
            ),
            task_service.create_task(
                title="30.10 normální",
                due_date=date(2026, 10, 30),
                priority=PRIORITY_NORMAL,
            ),
        ]
        wanted = {task.id for task in items}
        ordered, upcoming = self._ordered_ids(wanted)
        self.assertEqual(ordered, [task.id for task in items])
        self.assertEqual(upcoming, ordered)


if __name__ == "__main__":
    unittest.main()
