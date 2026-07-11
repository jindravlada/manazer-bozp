"""Fáze 97a – dolaď Dashboard (výšky, termíny, tooltip, zdroj Ručně)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_calendar_placeholder import CalendarPlaceholderWidget
    from core.dashboard.widget_recent_activity import RecentActivityWidget
    from core.dashboard.widget_upcoming_tasks import (
        COL_SOURCE,
        COL_TITLE,
        UpcomingTasksWidget,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class DashboardPhase97aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def test_attention_panel_taller_activity_shorter(self) -> None:
        page = DashboardPage()
        self.assertGreaterEqual(page.upcoming.minimumHeight(), 340)
        self.assertLessEqual(page.activity.maximumHeight(), 160)
        self.assertLess(page.activity.maximumHeight(), page.upcoming.minimumHeight())

    def test_recent_activity_shows_three_items(self) -> None:
        for index in range(5):
            task_service.create_task(title=f"Aktivita {index}")
        widget = RecentActivityWidget()
        text = widget.content.text()
        self.assertEqual(text.count("Aktivita "), 3)
        # Nejnovější tři (4, 3, 2); starší (0, 1) už ne.
        self.assertIn("Aktivita 4", text)
        self.assertIn("Aktivita 3", text)
        self.assertIn("Aktivita 2", text)
        self.assertNotIn("Aktivita 0", text)

    def test_audit_uses_start_date_after_started(self) -> None:
        planned = date.today() + timedelta(days=10)
        started = date.today() - timedelta(days=1)
        audit = audit_service.create_audit(
            workplace_name="Hodonín",
            audit_date=planned,
            started_at=started,
        )
        match = next(
            item for item in get_attention_items() if item.entity_id == audit.id
        )
        self.assertEqual(match.due_date, started)

    def test_audit_uses_planned_date_before_start(self) -> None:
        planned = date.today() + timedelta(days=8)
        audit = audit_service.create_audit(
            workplace_name="Plánovaný",
            audit_date=planned,
        )
        match = next(
            item for item in get_attention_items() if item.entity_id == audit.id
        )
        self.assertEqual(match.due_date, planned)

    def test_inspection_uses_start_date_after_started(self) -> None:
        planned = date.today() + timedelta(days=12)
        started = date.today()
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka start",
            inspection_date=planned,
            started_at=started,
        )
        match = next(
            item
            for item in get_attention_items()
            if item.entity_id == inspection.id
        )
        self.assertEqual(match.due_date, started)

    def test_manual_task_source_is_rucne(self) -> None:
        task = task_service.create_task(
            title="Ruční úkol 97a",
            due_date=date.today() + timedelta(days=1),
        )
        match = next(
            item for item in get_attention_items() if item.entity_id == task.id
        )
        self.assertEqual(match.source_label, "Ručně")

        widget = UpcomingTasksWidget()
        sources = [
            widget.table.item(row, COL_SOURCE).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertIn("Ručně", sources)
        self.assertGreater(
            widget.table.columnWidth(COL_TITLE),
            widget.table.columnWidth(COL_SOURCE),
        )

    def test_calendar_tooltip_lists_day_events(self) -> None:
        due = date.today() + timedelta(days=3)
        task_service.create_task(title="Objednat měření", due_date=due)
        audit_service.create_audit(
            workplace_name="Provoz Delta",
            audit_date=due,
        )
        panel = CalendarPlaceholderWidget()
        events = panel.calendar._day_events.get(due, [])
        self.assertTrue(
            any(label.startswith("Úkol – Objednat měření") for label in events)
        )
        self.assertTrue(any("Audit – Provoz Delta" in label for label in events))

        empty_day = due + timedelta(days=20)
        self.assertNotIn(empty_day, panel.calendar._day_events)

    def test_calendar_empty_day_hides_tooltip(self) -> None:
        panel = CalendarPlaceholderWidget()
        empty = date.today() + timedelta(days=40)
        self.assertNotIn(empty, panel.calendar._day_events)
        # Prázdný den nemá události → tooltip se nemá sestavit.
        self.assertFalse(bool(panel.calendar._day_events.get(empty)))


if __name__ == "__main__":
    unittest.main()
