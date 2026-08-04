"""MEETINGS-2d: úkoly navázané na body jednání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QLabel

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

    from core.shared.constants import ENTITY_MEETING
    from moduly.schuzky.constants import (
        ACTION_ADD_TASK,
        ACTION_UNLINK_TASK,
        SAVE_MEETING_BEFORE_TASK_MESSAGE,
        SECTION_CONCLUSION_TASKS,
        SECTION_ITEM_TASKS,
        SECTION_LINKED_TASKS,
    )
    from moduly.schuzky.sluzby.meeting_agenda_item_service import (
        meeting_agenda_item_service,
    )
    from moduly.schuzky.sluzby.meeting_item_task_service import (
        agenda_item_check_code,
        meeting_item_task_service,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service


class Meetings2dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _saved_meeting_with_items(self):
        meeting = meeting_service.create_meeting(title="Schůzka s úkoly bodů")
        saved = meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {"title": "Bod A", "zaver": "Závěr A"},
                {"title": "Bod B", "zaver": "Závěr B"},
            ],
        )
        return meeting, saved

    def test_create_task_bound_to_item(self) -> None:
        meeting, items = self._saved_meeting_with_items()
        item_a = items[0]
        task = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=item_a.id,
            title="Úkol z bodu A",
            due_date=date(2026, 9, 1),
        )
        self.assertEqual(task.source_module, ENTITY_MEETING)
        self.assertEqual(task.source_record_id, meeting.id)
        self.assertEqual(task.source_check_code, agenda_item_check_code(item_a.id))

        linked = meeting_item_task_service.list_for_item(meeting.id, item_a.id)
        self.assertEqual([t.id for t in linked], [task.id])
        self.assertEqual(
            meeting_item_task_service.list_for_item(meeting.id, items[1].id),
            [],
        )

    def test_open_and_switch_items(self) -> None:
        meeting, items = self._saved_meeting_with_items()
        task_a = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=items[0].id,
            title="Úkol A",
        )
        task_b = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=items[1].id,
            title="Úkol B",
        )

        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)
        self.assertEqual(widget.tasks_table.rowCount(), 1)
        self.assertEqual(widget.tasks_table.item(0, 0).text(), "Úkol A")
        self.assertEqual(widget._task_ids, [task_a.id])

        widget.table.selectRow(1)
        self.assertEqual(widget.tasks_table.rowCount(), 1)
        self.assertEqual(widget.tasks_table.item(0, 0).text(), "Úkol B")
        self.assertEqual(widget._task_ids, [task_b.id])

    def test_unlink_keeps_task(self) -> None:
        meeting, items = self._saved_meeting_with_items()
        task = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=items[0].id,
            title="Odpojitelný",
        )
        meeting_item_task_service.unlink_task(task.id)
        reloaded = task_service.get_task_by_id(task.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Odpojitelný")
        self.assertEqual(reloaded.source_module, "manual")
        self.assertIsNone(reloaded.source_record_id)
        self.assertEqual(reloaded.source_check_code, "")
        self.assertEqual(
            meeting_item_task_service.list_for_item(meeting.id, items[0].id),
            [],
        )

    def test_unsaved_item_blocks_create(self) -> None:
        widget = MeetingAgendaItemsWidget()
        widget._meeting_id = 1
        widget.add_item()
        with patch("moduly.schuzky.ui.meeting_agenda_items_widget.QMessageBox") as box:
            widget.add_task()
        box.information.assert_called_once()
        self.assertEqual(
            box.information.call_args.args[2],
            SAVE_MEETING_BEFORE_TASK_MESSAGE,
        )

    def test_create_via_task_dialog_prefill_source_only(self) -> None:
        meeting, items = self._saved_meeting_with_items()
        widget = MeetingAgendaItemsWidget()
        widget.load_for_meeting(meeting.id)

        class FakeTaskDialog:
            def __init__(self, parent=None, task=None):
                self._title = ""

            def exec(self):
                return QDialog.DialogCode.Accepted

            def get_data(self):
                return {
                    "title": "Vědomě zadaný název",
                    "description": "",
                    "priority": "Normální",
                    "due_date": date.today(),
                    "responsible_person_id": None,
                    "workplace_id": None,
                    "completed": False,
                    "completed_date": None,
                    "check_due_date": None,
                    "checked_date": None,
                    "checked_by_id": None,
                    "canceled": False,
                    "note": "",
                    "requires_verification": False,
                }

        with patch(
            "moduly.schuzky.ui.meeting_agenda_items_widget.TaskDialog",
            FakeTaskDialog,
        ):
            widget.add_task()

        tasks = meeting_item_task_service.list_for_item(meeting.id, items[0].id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Vědomě zadaný název")
        self.assertEqual(tasks[0].source_record_id, meeting.id)
        self.assertEqual(
            tasks[0].source_check_code,
            agenda_item_check_code(items[0].id),
        )

    def test_item_ids_stable_after_resave(self) -> None:
        meeting, items = self._saved_meeting_with_items()
        item_id = items[0].id
        meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=item_id,
            title="Stabilní vazba",
        )
        meeting_agenda_item_service.save_items(
            meeting.id,
            [
                {
                    "id": items[0].id,
                    "title": "Bod A upraven",
                    "zaver": "Závěr A",
                },
                {
                    "id": items[1].id,
                    "title": "Bod B",
                    "zaver": "Závěr B",
                },
            ],
        )
        reloaded = meeting_agenda_item_service.get_for_meeting(meeting.id)
        self.assertEqual(reloaded[0].id, item_id)
        linked = meeting_item_task_service.list_for_item(meeting.id, item_id)
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].title, "Stabilní vazba")

    def test_dialog_has_item_tasks_not_legacy_sections(self) -> None:
        meeting, _items = self._saved_meeting_with_items()
        dialog = MeetingDialog(meeting=meeting)
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        self.assertIn(SECTION_ITEM_TASKS, labels)
        self.assertNotIn(SECTION_CONCLUSION_TASKS, labels)
        self.assertNotIn(SECTION_LINKED_TASKS, labels)
        self.assertEqual(
            dialog.agenda_items_widget.add_task_btn.text(),
            ACTION_ADD_TASK,
        )
        self.assertEqual(
            dialog.agenda_items_widget.unlink_task_btn.text(),
            ACTION_UNLINK_TASK,
        )


if __name__ == "__main__":
    unittest.main()
