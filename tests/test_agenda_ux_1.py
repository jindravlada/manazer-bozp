"""AGENDA-UX-1: sjednocení UX s modulem Úkoly."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

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

    from moduly.agenda.constants import (
        COL_TITLE,
        COLUMN_HEADERS,
        DEFAULT_STATUS_MODE,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        PRIORITY_COLORS,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_NORMAL,
        ROW_LEGEND,
        ROW_STATE_CANCELED,
        ROW_STATE_DONE,
        ROW_STATE_OVERDUE,
        ROW_STATE_WAITING,
        STATUS_MODE_ACTIVE,
        STATUS_MODE_ALL,
        STATUS_MODE_CLOSED,
        STATUS_MODE_DONE,
        STATUS_MODE_PLANNED,
        STATUS_MODES_BOTH,
        STATUS_MODES_MEETINGS_ONLY,
        STATUS_MODES_TASKS_ONLY,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import (
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.ukoly_page import UkolyPage


class AgendaUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") == STATUS_CANCELLED:
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                event_type=getattr(meeting, "event_type", None) or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
                proceedings=meeting.proceedings or "",
                conclusions=meeting.conclusions or "",
                notes=meeting.notes or "",
            )
        for task in list(task_service.get_all_tasks()):
            if task.computed_status != "Zrušeno":
                task_service.cancel_task(task.id)

    def test_default_filter(self) -> None:
        page = AgendaPage()
        self.assertTrue(page.type_checks[ITEM_TYPE_TASK].isChecked())
        self.assertTrue(page.type_checks[ITEM_TYPE_MEETING].isChecked())
        self.assertEqual(page.status_filter.currentText(), DEFAULT_STATUS_MODE)
        self.assertEqual(DEFAULT_STATUS_MODE, STATUS_MODE_ACTIVE)
        self.assertIsInstance(page.status_filter, QComboBox)
        modes = [page.status_filter.itemText(i) for i in range(page.status_filter.count())]
        self.assertEqual(modes, list(STATUS_MODES_BOTH))

    def test_status_mode_switching(self) -> None:
        from PySide6.QtCore import Qt

        active_task = task_service.create_task(
            title="Aktivní",
            due_date=date.today() + timedelta(days=2),
        )
        done_task = task_service.create_task(
            title="Hotovo",
            due_date=date.today() + timedelta(days=1),
        )
        task_service.mark_completed(done_task.id)
        planned = meeting_service.create_meeting(
            title="Plán",
            starts_at=datetime.now() + timedelta(days=2),
            status=STATUS_PLANNED,
        )
        closed = meeting_service.create_meeting(
            title="Uzavřeno",
            starts_at=datetime.now() - timedelta(days=1),
            status=STATUS_CLOSED,
        )

        page = AgendaPage()

        def _keys():
            return {
                (
                    page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole).item_type,
                    page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole).source_id,
                )
                for row in range(page.table.rowCount())
            }

        page.status_filter.setCurrentText(STATUS_MODE_ACTIVE)
        page.refresh()
        self.assertIn((ITEM_TYPE_TASK, active_task.id), _keys())
        self.assertIn((ITEM_TYPE_MEETING, planned.id), _keys())
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), _keys())
        self.assertNotIn((ITEM_TYPE_MEETING, closed.id), _keys())

        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.type_checks[ITEM_TYPE_MEETING].setChecked(False)
        page.refresh()
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), _keys())
        self.assertNotIn((ITEM_TYPE_TASK, active_task.id), _keys())

        page.type_checks[ITEM_TYPE_MEETING].setChecked(True)
        page.type_checks[ITEM_TYPE_TASK].setChecked(False)
        page.status_filter.setCurrentText(STATUS_MODE_CLOSED)
        page.refresh()
        self.assertEqual(_keys(), {(ITEM_TYPE_MEETING, closed.id)})

        page.type_checks[ITEM_TYPE_TASK].setChecked(True)
        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        self.assertTrue(
            {
                (ITEM_TYPE_TASK, active_task.id),
                (ITEM_TYPE_MEETING, planned.id),
                (ITEM_TYPE_MEETING, closed.id),
            }.issubset(_keys())
        )
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), _keys())

    def test_status_modes_depend_on_type(self) -> None:
        page = AgendaPage()
        page.type_checks[ITEM_TYPE_MEETING].setChecked(False)
        modes = [page.status_filter.itemText(i) for i in range(page.status_filter.count())]
        self.assertEqual(modes, list(STATUS_MODES_TASKS_ONLY))

        page.type_checks[ITEM_TYPE_TASK].setChecked(False)
        page.type_checks[ITEM_TYPE_MEETING].setChecked(True)
        modes = [page.status_filter.itemText(i) for i in range(page.status_filter.count())]
        self.assertEqual(modes, list(STATUS_MODES_MEETINGS_ONLY))
        self.assertIn(STATUS_MODE_PLANNED, modes)

    def test_row_colors_match_priority(self) -> None:
        overdue = task_service.create_task(
            title="Po termínu",
            due_date=date.today() - timedelta(days=1),
            priority=PRIORITY_CRITICAL,
        )
        waiting = task_service.create_task(
            title="Čeká kontrola",
            due_date=date.today() + timedelta(days=5),
            completed=True,
            completed_date=date.today(),
            requires_verification=True,
            check_due_date=date.today() + timedelta(days=10),
            priority=PRIORITY_HIGH,
        )
        done = task_service.create_task(
            title="Hotovo",
            due_date=date.today() + timedelta(days=1),
            priority=PRIORITY_NORMAL,
        )
        task_service.mark_completed(done.id)
        cancelled_meeting = meeting_service.create_meeting(
            title="Zrušeno",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_CANCELLED,
            priority=PRIORITY_NORMAL,
        )
        closed = meeting_service.create_meeting(
            title="Uzavřeno",
            starts_at=datetime.now() - timedelta(days=2),
            status=STATUS_CLOSED,
            priority=PRIORITY_CRITICAL,
        )

        items = { (i.item_type, i.source_id): i for i in agenda_service.get_items() }
        self.assertEqual(items[(ITEM_TYPE_TASK, overdue.id)].row_state, ROW_STATE_OVERDUE)
        self.assertEqual(items[(ITEM_TYPE_TASK, waiting.id)].row_state, ROW_STATE_WAITING)
        self.assertNotIn((ITEM_TYPE_TASK, done.id), items)
        self.assertEqual(
            items[(ITEM_TYPE_MEETING, cancelled_meeting.id)].row_state,
            ROW_STATE_CANCELED,
        )
        self.assertEqual(items[(ITEM_TYPE_MEETING, closed.id)].row_state, ROW_STATE_DONE)
        self.assertEqual(items[(ITEM_TYPE_TASK, overdue.id)].priority, PRIORITY_CRITICAL)
        self.assertEqual(items[(ITEM_TYPE_MEETING, closed.id)].priority, PRIORITY_CRITICAL)

        page = AgendaPage()
        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        from PySide6.QtCore import Qt

        found_task = False
        found_meeting = False
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            color = page.table.item(row, COL_TITLE).background().color()
            if payload.source_id == overdue.id and payload.item_type == ITEM_TYPE_TASK:
                self.assertEqual(color, QColor(PRIORITY_COLORS[PRIORITY_CRITICAL]))
                found_task = True
            if payload.source_id == closed.id and payload.item_type == ITEM_TYPE_MEETING:
                self.assertEqual(color, QColor(PRIORITY_COLORS[PRIORITY_CRITICAL]))
                found_meeting = True
        self.assertTrue(found_task, "critical task row not found")
        self.assertTrue(found_meeting, "critical meeting row not found")

    def test_legend_shows_priority(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.legend.text(), ROW_LEGEND)
        self.assertIn("Kritická", ROW_LEGEND)
        self.assertIn("Normální", ROW_LEGEND)
        ukoly = UkolyPage()
        task_legends = [
            label.text()
            for label in ukoly.findChildren(QLabel)
            if "červená = po termínu" in label.text()
        ]
        self.assertEqual(len(task_legends), 1)
        self.assertNotEqual(task_legends[0], ROW_LEGEND)

    def test_combined_active_view(self) -> None:
        task = task_service.create_task(
            title="Společně úkol",
            due_date=date.today() + timedelta(days=1),
        )
        meeting = meeting_service.create_meeting(
            title="Společně událost",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
        )
        done = task_service.create_task(
            title="Hotové mimo aktivní",
            due_date=date.today() + timedelta(days=1),
        )
        task_service.mark_completed(done.id)

        page = AgendaPage()
        self.assertEqual(page.status_filter.currentText(), STATUS_MODE_ACTIVE)
        from PySide6.QtCore import Qt

        ids = {
            (
                page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole).item_type,
                page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole).source_id,
            )
            for row in range(page.table.rowCount())
        }
        self.assertIn((ITEM_TYPE_TASK, task.id), ids)
        self.assertIn((ITEM_TYPE_MEETING, meeting.id), ids)
        self.assertNotIn((ITEM_TYPE_TASK, done.id), ids)

    def test_column_order(self) -> None:
        self.assertEqual(
            COLUMN_HEADERS,
            [
                "Název",
                "Termín",
                "Odpovědná osoba / Organizátor",
                "Stav",
                "Zdroj",
                "Typ",
            ],
        )
        page = AgendaPage()
        headers = [
            page.table.horizontalHeaderItem(i).text()
            for i in range(page.table.columnCount())
            if not page.table.isColumnHidden(i)
        ]
        self.assertEqual(headers, list(COLUMN_HEADERS))


if __name__ == "__main__":
    unittest.main()
