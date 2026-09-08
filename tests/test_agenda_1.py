"""AGENDA-1: společný přehled úkolů a událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
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

    from core.modules.module_manager import ModuleManager
    from moduly.agenda.constants import (
        ITEM_TYPE_MEETING,
        ITEM_TYPE_TASK,
        MODULE_KEY,
        MODULE_NAME,
        STATUS_MODE_ACTIVE,
        STATUS_MODE_ALL,
        STATUS_MODE_DONE,
        TYPE_FILTER_MEETINGS,
        TYPE_FILTER_TASKS,
    )
    from moduly.agenda.sluzby.agenda_service import (
        agenda_service,
        filter_agenda_items,
    )
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.schuzky.constants import DEFAULT_MEETING_STATUS, STATUS_CANCELLED, STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class Agenda1TestCase(unittest.TestCase):
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

    def test_module_registered_in_menu(self) -> None:
        modules = {m.key: m for m in ModuleManager().get_modules()}
        self.assertIn(MODULE_KEY, modules)
        self.assertEqual(modules[MODULE_KEY].name, MODULE_NAME)

    def test_combined_display(self) -> None:
        task = task_service.create_task(
            title="Úkol v agendě",
            due_date=date(2026, 8, 12),
        )
        meeting = meeting_service.create_meeting(
            title="Událost v agendě",
            starts_at=datetime(2026, 8, 11, 9, 0),
            status=DEFAULT_MEETING_STATUS,
        )
        items = agenda_service.get_items()
        pairs = {(i.item_type, i.source_id) for i in items}
        self.assertIn((ITEM_TYPE_TASK, task.id), pairs)
        self.assertIn((ITEM_TYPE_MEETING, meeting.id), pairs)

        page = AgendaPage()
        page.refresh()
        titles = [
            page.table.item(row, 0).text()
            for row in range(page.table.rowCount())
        ]
        self.assertTrue(any("Úkol v agendě" in t for t in titles))
        self.assertTrue(any("Událost v agendě" in t for t in titles))

    def test_type_filters(self) -> None:
        task = task_service.create_task(title="Jen úkol", due_date=date(2026, 8, 12))
        meeting = meeting_service.create_meeting(
            title="Jen událost",
            starts_at=datetime(2026, 8, 12, 10, 0),
            status=STATUS_PLANNED,
        )
        all_items = agenda_service.get_items()
        only_tasks = filter_agenda_items(
            all_items,
            type_filters={ITEM_TYPE_TASK},
            status_mode=STATUS_MODE_ACTIVE,
        )
        native_tasks = [i for i in only_tasks if i.item_type in {ITEM_TYPE_TASK, ITEM_TYPE_MEETING}]
        self.assertEqual({i.source_id for i in native_tasks}, {task.id})
        self.assertTrue(all(i.item_type == ITEM_TYPE_TASK for i in native_tasks))
        self.assertFalse(any(i.item_type == ITEM_TYPE_MEETING for i in only_tasks))

        only_meetings = filter_agenda_items(
            all_items,
            type_filters={ITEM_TYPE_MEETING},
            status_mode=STATUS_MODE_ACTIVE,
        )
        native_meetings = [
            i for i in only_meetings if i.item_type in {ITEM_TYPE_TASK, ITEM_TYPE_MEETING}
        ]
        self.assertEqual({i.source_id for i in native_meetings}, {meeting.id})
        self.assertFalse(any(i.item_type == ITEM_TYPE_TASK for i in only_meetings))

        page = AgendaPage()
        page.type_checks[ITEM_TYPE_MEETING].setChecked(False)
        page.refresh()
        types = {
            page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).item_type
            for row in range(page.table.rowCount())
        }
        self.assertNotIn(ITEM_TYPE_MEETING, types)
        self.assertIn(ITEM_TYPE_TASK, types)
        self.assertEqual(page.type_checks[ITEM_TYPE_TASK].text(), TYPE_FILTER_TASKS)
        self.assertEqual(page.type_checks[ITEM_TYPE_MEETING].text(), TYPE_FILTER_MEETINGS)

    def test_status_filters(self) -> None:
        open_task = task_service.create_task(
            title="Otevřený úkol",
            due_date=date.today() + timedelta(days=3),
        )
        done_task = task_service.create_task(
            title="Hotový úkol",
            due_date=date.today() + timedelta(days=1),
        )
        task_service.mark_completed(done_task.id)

        planned = meeting_service.create_meeting(
            title="Plán",
            starts_at=datetime.now() + timedelta(days=2),
            status=STATUS_PLANNED,
        )

        page = AgendaPage()
        page.status_filter.setCurrentText(STATUS_MODE_ACTIVE)
        page.refresh()

        payloads = [
            page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(page.table.rowCount())
        ]
        ids = {(p.item_type, p.source_id) for p in payloads}
        self.assertIn((ITEM_TYPE_TASK, open_task.id), ids)
        self.assertIn((ITEM_TYPE_MEETING, planned.id), ids)
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), ids)

        page.type_checks[ITEM_TYPE_MEETING].setChecked(False)
        page.status_filter.setCurrentText(STATUS_MODE_DONE)
        page.refresh()
        payloads = [
            page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(page.table.rowCount())
        ]
        done_ids = {(p.item_type, p.source_id) for p in payloads}
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), done_ids)
        self.assertNotIn((ITEM_TYPE_TASK, open_task.id), done_ids)

        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()
        payloads = [
            page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(page.table.rowCount())
        ]
        all_ids = {(p.item_type, p.source_id) for p in payloads}
        self.assertIn((ITEM_TYPE_TASK, open_task.id), all_ids)
        self.assertNotIn((ITEM_TYPE_TASK, done_task.id), all_ids)

    def test_open_correct_editor(self) -> None:
        task = task_service.create_task(
            title="Editor úkolu",
            due_date=date.today() + timedelta(days=1),
        )
        meeting = meeting_service.create_meeting(
            title="Editor události",
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
        )
        page = AgendaPage()
        page.refresh()

        opened: list[str] = []

        def _open_task(task_id: int) -> None:
            opened.append(f"task:{task_id}")

        def _open_meeting(meeting_id: int) -> None:
            opened.append(f"meeting:{meeting_id}")

        page._open_task = _open_task  # type: ignore[method-assign]
        page._open_meeting = _open_meeting  # type: ignore[method-assign]

        for row in range(page.table.rowCount()):
            payload = page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload.source_id == task.id and payload.item_type == ITEM_TYPE_TASK:
                page.table.selectRow(row)
                page.edit_selected()
                break
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload.source_id == meeting.id and payload.item_type == ITEM_TYPE_MEETING:
                page.table.selectRow(row)
                page.edit_selected()
                break

        self.assertEqual(opened, [f"task:{task.id}", f"meeting:{meeting.id}"])

    def test_chronological_order(self) -> None:
        later_task = task_service.create_task(
            title="Později",
            due_date=date(2026, 8, 20),
        )
        early_meeting = meeting_service.create_meeting(
            title="Dříve",
            starts_at=datetime(2026, 8, 10, 8, 0),
            status=STATUS_PLANNED,
        )
        mid_task = task_service.create_task(
            title="Uprostřed",
            due_date=date(2026, 8, 15),
        )

        wanted = {
            (ITEM_TYPE_MEETING, early_meeting.id),
            (ITEM_TYPE_TASK, mid_task.id),
            (ITEM_TYPE_TASK, later_task.id),
        }
        items = [
            i
            for i in agenda_service.get_items()
            if (i.item_type, i.source_id) in wanted
        ]
        self.assertEqual(
            [(i.item_type, i.source_id) for i in items],
            [
                (ITEM_TYPE_MEETING, early_meeting.id),
                (ITEM_TYPE_TASK, mid_task.id),
                (ITEM_TYPE_TASK, later_task.id),
            ],
        )

        page = AgendaPage()
        page.refresh()
        ordered = [
            (
                page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).item_type,
                page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).source_id,
            )
            for row in range(page.table.rowCount())
            if (
                page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).item_type,
                page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).source_id,
            )
            in wanted
        ]
        self.assertEqual(
            ordered,
            [
                (ITEM_TYPE_MEETING, early_meeting.id),
                (ITEM_TYPE_TASK, mid_task.id),
                (ITEM_TYPE_TASK, later_task.id),
            ],
        )

    def test_refresh_after_save(self) -> None:
        page = AgendaPage()
        page.refresh()
        before = page.table.rowCount()

        meeting = meeting_service.create_meeting(
            title="Po uložení",
            starts_at=datetime.now() + timedelta(days=4),
            status=STATUS_PLANNED,
        )
        page.refresh()
        found = any(
            page.table.item(row, 0).data(Qt.ItemDataRole.UserRole).source_id == meeting.id
            for row in range(page.table.rowCount())
        )
        self.assertTrue(found)
        self.assertGreaterEqual(page.table.rowCount(), before + 1)


if __name__ == "__main__":
    unittest.main()
