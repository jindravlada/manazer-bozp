"""DASHBOARD-UX-1: naléhavost úkolu v „Co hoří“ podle aktuální fáze."""

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

    from core.dashboard.widget_today import (
        STATUS_WAITING_CHECK,
        TodayWidget,
        classify_burning_tasks,
        task_urgency_due_date,
    )
    from moduly.ukoly.sluzby.task_service import task_service


class DashboardUx1BurningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)

    def test_active_overdue_uses_due_date(self) -> None:
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="Nesplněný po termínu",
            due_date=date(2026, 8, 31),
            requires_verification=False,
        )
        self.assertEqual(task.computed_status, "Aktivní")
        self.assertEqual(task_urgency_due_date(task), date(2026, 8, 31))

        burning, due_today, waiting = classify_burning_tasks([task], today)
        self.assertEqual([item.id for item in burning], [task.id])
        self.assertEqual(due_today, [])
        self.assertEqual(waiting, [])

    def test_waiting_check_ignores_completion_due_date(self) -> None:
        """Příklad: splněno před 31. 8., potvrzení do 30. 10. → 31. 8. se ignoruje."""
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="Splněno čeká potvrzení",
            due_date=date(2026, 8, 31),
            completed=True,
            completed_date=date(2026, 8, 20),
            requires_verification=True,
            check_due_date=date(2026, 10, 30),
        )
        self.assertEqual(task.computed_status, STATUS_WAITING_CHECK)
        self.assertEqual(task_urgency_due_date(task), date(2026, 10, 30))

        burning, due_today, waiting = classify_burning_tasks([task], today)
        self.assertEqual(burning, [])
        self.assertEqual(due_today, [])
        self.assertEqual([item.id for item in waiting], [task.id])

    def test_waiting_check_burns_on_confirmation_deadline(self) -> None:
        today = date(2026, 11, 1)
        task = task_service.create_task(
            title="Po termínu potvrzení",
            due_date=date(2026, 8, 31),
            completed=True,
            completed_date=date(2026, 8, 20),
            requires_verification=True,
            check_due_date=date(2026, 10, 30),
        )
        burning, due_today, waiting = classify_burning_tasks([task], today)
        self.assertEqual([item.id for item in burning], [task.id])
        self.assertEqual(due_today, [])
        self.assertEqual(waiting, [])

    def test_confirmed_task_excluded(self) -> None:
        today = date(2026, 9, 1)
        task = task_service.create_task(
            title="Potvrzený úkol",
            due_date=date(2026, 8, 10),
            completed=True,
            completed_date=date(2026, 8, 5),
            requires_verification=True,
            check_due_date=date(2026, 8, 20),
            checked_date=date(2026, 8, 15),
        )
        self.assertEqual(task.computed_status, "Ukončeno")
        self.assertIsNone(task_urgency_due_date(task))

        burning, due_today, waiting = classify_burning_tasks([task], today)
        self.assertEqual(burning, [])
        self.assertEqual(due_today, [])
        self.assertEqual(waiting, [])

    def test_widget_shows_check_due_not_completion_due(self) -> None:
        task_service.create_task(
            title="Widget potvrzení",
            due_date=date(2026, 8, 31),
            completed=True,
            completed_date=date(2026, 8, 20),
            requires_verification=True,
            check_due_date=date(2026, 10, 30),
        )
        widget = TodayWidget()
        widget.refresh(today=date(2026, 9, 1))
        text = widget.content.text()
        self.assertIn("Widget potvrzení", text)
        self.assertIn("30.10.2026", text)
        self.assertNotIn("31.08.2026", text)
        self.assertIn("🟡", text)
        self.assertNotIn("🔴", text)
        widget.close()


if __name__ == "__main__":
    unittest.main()
