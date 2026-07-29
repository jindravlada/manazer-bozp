"""DASHBOARD-1: Nadcházející události a úkoly."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="dashboard-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_AUDIT,
        ITEM_TYPE_INSPECTION,
        ITEM_TYPE_TASK,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_upcoming_tasks import COL_DUE, UpcomingTasksWidget
    from core.windows.main_window import MainWindow
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class Dashboard1UpcomingItemsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def test_common_list_contains_audit_inspection_task(self) -> None:
        started = date.today() + timedelta(days=3)
        audit = audit_service.create_audit(workplace_name="Audit A", started_at=started)
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka B",
            started_at=started + timedelta(days=1),
        )
        task = task_service.create_task(
            title="Úkol C",
            due_date=started + timedelta(days=2),
        )
        items = get_attention_items()
        by_id = {(item.item_type, item.source_id): item for item in items}
        self.assertIn((ITEM_TYPE_AUDIT, audit.id), by_id)
        self.assertIn((ITEM_TYPE_INSPECTION, inspection.id), by_id)
        self.assertIn((ITEM_TYPE_TASK, task.id), by_id)

    def test_audit_without_start_date_is_hidden_and_with_start_shown(self) -> None:
        hidden = audit_service.create_audit(workplace_name="Bez zahájení")
        shown = audit_service.create_audit(
            workplace_name="Se zahájením",
            started_at=date.today() + timedelta(days=1),
        )
        ids = [item.source_id for item in get_attention_items() if item.item_type == ITEM_TYPE_AUDIT]
        self.assertNotIn(hidden.id, ids)
        self.assertIn(shown.id, ids)

    def test_inspection_without_start_date_is_hidden_and_with_start_shown(self) -> None:
        hidden = bozp_inspection_service.create_inspection(workplace_name="Bez zahájení")
        shown = bozp_inspection_service.create_inspection(
            workplace_name="Se zahájením",
            started_at=date.today() + timedelta(days=1),
        )
        ids = [
            item.source_id for item in get_attention_items() if item.item_type == ITEM_TYPE_INSPECTION
        ]
        self.assertNotIn(hidden.id, ids)
        self.assertIn(shown.id, ids)

    def test_chronological_sorting_and_overdue_label(self) -> None:
        today = date.today()
        bozp_inspection_service.create_inspection(workplace_name="I1", started_at=today + timedelta(days=3))
        task_service.create_task(title="T1", due_date=today - timedelta(days=1))
        audit_service.create_audit(workplace_name="A1", started_at=today + timedelta(days=1))
        items = get_attention_items()
        dates = [item.date for item in items if item.date is not None]
        self.assertEqual(dates, sorted(dates))

        widget = UpcomingTasksWidget()
        overdue_row = next(
            row
            for row in range(widget.table.rowCount())
            if "Po termínu" in widget.table.item(row, COL_DUE).text()
        )
        self.assertGreaterEqual(overdue_row, 0)

    def test_start_date_change_and_removal_reflect_after_refresh(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Audit měněný",
            started_at=date.today() + timedelta(days=5),
        )
        first_date = next(
            item.date for item in get_attention_items() if item.item_type == ITEM_TYPE_AUDIT and item.source_id == audit.id
        )
        self.assertEqual(first_date, date.today() + timedelta(days=5))

        audit_service.update_audit(audit.id, started_at=date.today() + timedelta(days=1))
        changed_date = next(
            item.date for item in get_attention_items() if item.item_type == ITEM_TYPE_AUDIT and item.source_id == audit.id
        )
        self.assertEqual(changed_date, date.today() + timedelta(days=1))

        audit_service.update_audit(audit.id, started_at=None)
        self.assertFalse(
            any(item.item_type == ITEM_TYPE_AUDIT and item.source_id == audit.id for item in get_attention_items())
        )

    def test_opening_uses_source_id_for_all_types(self) -> None:
        opened: list[tuple[str, int]] = []

        def on_open(item):
            opened.append((item.source_type, item.source_id))

        audit = audit_service.create_audit(workplace_name="Audit O", started_at=date.today())
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka O",
            started_at=date.today() + timedelta(days=1),
        )
        task = task_service.create_task(title="Úkol O", due_date=date.today() + timedelta(days=2))

        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        targets = {
            (ITEM_TYPE_AUDIT, audit.id),
            (ITEM_TYPE_INSPECTION, inspection.id),
            (ITEM_TYPE_TASK, task.id),
        }
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            pair = (payload.source_type, payload.source_id)
            if pair in targets:
                widget.table.selectRow(row)
                widget._open_selected()
        self.assertEqual(set(opened), targets)

    def test_empty_state_message_is_visible(self) -> None:
        widget = UpcomingTasksWidget()
        self.assertEqual(widget.table.rowCount(), 0)
        self.assertIn("Nejsou evidovány žádné nadcházející události ani úkoly.", widget.empty_label.text())

    def test_missing_audit_or_inspection_source_shows_warning(self) -> None:
        dashboard = SimpleNamespace(refresh=MagicMock())
        dummy = SimpleNamespace(_page_widgets={"dashboard": dashboard}, _show=MagicMock())

        with patch.object(QMessageBox, "warning") as warn:
            MainWindow._open_audit_by_id(dummy, 999999)
        self.assertTrue(warn.called)
        dashboard.refresh.assert_called()

        dashboard.refresh.reset_mock()
        with patch.object(QMessageBox, "warning") as warn:
            MainWindow._open_inspection_by_id(dummy, 999999)
        self.assertTrue(warn.called)
        dashboard.refresh.assert_called()


if __name__ == "__main__":
    unittest.main()
