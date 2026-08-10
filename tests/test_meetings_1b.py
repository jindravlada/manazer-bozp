"""MEETINGS-1b: schůzky v Nadcházejících událostech a úkolech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

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
        ITEM_TYPE_AUDIT,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import (
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


def _meeting_items():
    return [
        item
        for item in get_attention_items()
        if item.item_type == ITEM_TYPE_MEETING
    ]


class Meetings1bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.organizer = person_service.create_person(
            first_name="Eva",
            last_name="Organizátorka",
        )

    def test_meeting_without_start_not_shown(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Bez data",
            starts_at=None,
            status=STATUS_PLANNED,
        )
        ids = [item.source_id for item in _meeting_items()]
        self.assertNotIn(meeting.id, ids)

    def test_planned_meeting_with_start_shown(self) -> None:
        starts = datetime.now() + timedelta(days=2, hours=3)
        ends = starts + timedelta(hours=1)
        meeting = meeting_service.create_meeting(
            title="Plánovaná schůzka",
            starts_at=starts,
            ends_at=ends,
            location="Místnost 1",
            organizer_person_id=self.organizer.id,
            status=STATUS_PLANNED,
        )
        items = [item for item in _meeting_items() if item.source_id == meeting.id]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.item_type, ITEM_TYPE_MEETING)
        self.assertEqual(item.source_type, ITEM_TYPE_MEETING)
        self.assertEqual(item.source_id, meeting.id)
        self.assertEqual(item.title, "Schůzka – Plánovaná schůzka")
        self.assertEqual(item.event_at, starts)
        self.assertEqual(item.ends_at, ends)
        self.assertIn("Místnost 1", item.subtitle)
        self.assertIn(self.organizer.display_name, item.subtitle)

        widget = UpcomingTasksWidget()
        found = False
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                found = True
                due_text = widget.table.item(row, 1).text()
                self.assertNotIn("Po termínu", due_text)
                self.assertEqual(widget.table.item(row, 0).text(), "Událost")
                self.assertEqual(
                    widget.table.item(row, 2).text(),
                    "Schůzka – Plánovaná schůzka",
                )
                self.assertIn("Místnost 1", widget.table.item(row, 4).text())
                break
        self.assertTrue(found)

    def test_held_meeting_not_shown(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Proběhlá legacy",
            starts_at=datetime.now() + timedelta(days=1),
            status="Proběhlo",
        )
        # Legacy Proběhlo se normalizuje na Uzavřeno → mimo attention.
        self.assertEqual(meeting.status, STATUS_CLOSED)
        self.assertNotIn(meeting.id, [item.source_id for item in _meeting_items()])

    def test_closed_meeting_not_shown(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Uzavřená",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_CLOSED,
        )
        self.assertNotIn(meeting.id, [item.source_id for item in _meeting_items()])

    def test_cancelled_meeting_not_shown(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Zrušená",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_CANCELLED,
        )
        self.assertNotIn(meeting.id, [item.source_id for item in _meeting_items()])

    def test_past_planned_meeting_marked_overdue(self) -> None:
        starts = datetime.now() - timedelta(hours=2)
        meeting = meeting_service.create_meeting(
            title="Po termínu schůzka",
            starts_at=starts,
            status=STATUS_PLANNED,
        )
        items = [item for item in _meeting_items() if item.source_id == meeting.id]
        self.assertEqual(len(items), 1)

        widget = UpcomingTasksWidget()
        due_text = None
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                due_text = widget.table.item(row, 1).text()
                break
        self.assertIsNotNone(due_text)
        self.assertIn("Po termínu", due_text)

    def test_meeting_sorted_chronologically_with_tasks(self) -> None:
        today = date.today()
        early_task = task_service.create_task(
            title="Úkol ráno",
            due_date=today,
            priority="Normální",
        )
        late_task = task_service.create_task(
            title="Úkol zítra",
            due_date=today + timedelta(days=1),
            priority="Normální",
        )
        meeting = meeting_service.create_meeting(
            title="Schůzka odpoledne",
            starts_at=datetime.combine(today, datetime.min.time()).replace(hour=14),
            status=STATUS_PLANNED,
        )
        audit = audit_service.create_audit(
            workplace_name="Audit po schůzce",
            started_at=today + timedelta(days=2),
        )

        expected = [
            (ITEM_TYPE_TASK, early_task.id),
            (ITEM_TYPE_MEETING, meeting.id),
            (ITEM_TYPE_TASK, late_task.id),
            (ITEM_TYPE_AUDIT, audit.id),
        ]
        items = get_attention_items(today=today)
        relevant = [
            (item.item_type, item.source_id)
            for item in items
            if (item.item_type, item.source_id) in expected
        ]
        self.assertEqual(relevant, expected)

    def test_open_uses_source_id(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Otevři podle ID",
            starts_at=datetime.now() + timedelta(days=3),
            status=STATUS_PLANNED,
        )
        opened: list[tuple[str, int]] = []

        def on_open(item) -> None:
            opened.append((item.source_type, item.source_id))

        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                widget.table.selectRow(row)
                widget._open_selected()
                break
        self.assertEqual(opened, [(ITEM_TYPE_MEETING, meeting.id)])

    def test_date_change_visible_after_refresh(self) -> None:
        starts = datetime.now() + timedelta(days=5, hours=9)
        meeting = meeting_service.create_meeting(
            title="Přesun schůzky",
            starts_at=starts,
            status=STATUS_PLANNED,
        )
        widget = UpcomingTasksWidget()
        before = None
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                before = widget.table.item(row, 1).text()
                break
        self.assertIsNotNone(before)

        new_starts = starts + timedelta(days=2)
        meeting_service.update_meeting(
            meeting.id,
            title="Přesun schůzky",
            starts_at=new_starts,
            status=STATUS_PLANNED,
        )
        widget.refresh()
        after = None
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                after = widget.table.item(row, 1).text()
                self.assertEqual(payload.event_at, new_starts)
                break
        self.assertIsNotNone(after)
        self.assertNotEqual(before, after)

    def test_status_change_removes_from_dashboard(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Změní se stav",
            starts_at=datetime.now() + timedelta(days=4),
            status=STATUS_PLANNED,
        )
        self.assertIn(meeting.id, [item.source_id for item in _meeting_items()])

        meeting_service.update_meeting(
            meeting.id,
            title="Změní se stav",
            starts_at=datetime.now() + timedelta(days=4),
            status=STATUS_CLOSED,
        )
        self.assertNotIn(meeting.id, [item.source_id for item in _meeting_items()])

    def test_missing_meeting_refresh_after_warning(self) -> None:
        from core.windows.main_window import MainWindow

        window = MagicMock(spec=MainWindow)
        window._page_widgets = {"dashboard": MagicMock()}
        window._page_widgets["dashboard"].refresh = MagicMock()

        with patch(
            "moduly.schuzky.sluzby.meeting_service.meeting_service.get_by_id",
            return_value=None,
        ), patch.object(QMessageBox, "warning") as warning:
            MainWindow._open_meeting_by_id(window, 999999)

        warning.assert_called_once()
        window._page_widgets["dashboard"].refresh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
