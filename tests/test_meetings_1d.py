"""MEETINGS-1d: vytvoření úkolů ze závěrů jednání."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

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
        ACTION_CREATE_TASK,
        ACTION_OPEN_TASK,
        SAVE_MEETING_BEFORE_TASK_MESSAGE,
        SECTION_LINKED_TASKS,
    )
    from moduly.schuzky.sluzby.meeting_conclusion_tasks import (
        build_conclusion_task_view,
        conclusion_check_code,
        split_conclusion_lines,
    )
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_conclusion_tasks_widget import (
        MeetingConclusionTasksWidget,
    )
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service


class Meetings1dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_split_conclusions_by_enter_skips_blank(self) -> None:
        text = "První bod\n\n  Druhý bod  \n\n\nTřetí\n"
        self.assertEqual(
            split_conclusion_lines(text),
            ["První bod", "Druhý bod", "Třetí"],
        )

    def test_create_task_prefill_and_source_link(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Schůzka s úkoly",
            conclusions="Dokončit školení\nZkontrolovat OOPP",
        )
        line = "Dokončit školení"
        task = task_service.create_task(
            title=line,
            source_module=ENTITY_MEETING,
            source_record_id=meeting.id,
            source_check_code=conclusion_check_code(line),
        )
        self.assertEqual(task.source_module, ENTITY_MEETING)
        self.assertEqual(task.source_record_id, meeting.id)
        self.assertEqual(task.title, line)
        self.assertTrue(task.source_check_code.startswith("concl:"))

        view = build_conclusion_task_view(
            meeting.conclusions,
            meeting_id=meeting.id,
        )
        self.assertEqual(len(view.rows), 2)
        self.assertEqual(view.rows[0].text, "Dokončit školení")
        self.assertIsNotNone(view.rows[0].task)
        self.assertEqual(view.rows[0].task.id, task.id)
        self.assertEqual(view.rows[1].text, "Zkontrolovat OOPP")
        self.assertIsNone(view.rows[1].task)
        self.assertEqual(view.orphan_tasks, [])

    def test_widget_shows_open_after_create(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Widget open",
            conclusions="Bod A",
        )
        task = task_service.create_task(
            title="Bod A",
            source_module=ENTITY_MEETING,
            source_record_id=meeting.id,
            source_check_code=conclusion_check_code("Bod A"),
        )
        widget = MeetingConclusionTasksWidget()
        widget.configure(
            meeting_id=meeting.id,
            get_conclusions_text=lambda: "Bod A",
        )
        buttons = widget.findChildren(QPushButton)
        labels = [button.text() for button in buttons]
        self.assertIn(ACTION_OPEN_TASK, labels)
        self.assertNotIn(ACTION_CREATE_TASK, labels)
        self.assertEqual(task.source_record_id, meeting.id)

    def test_conclusion_change_keeps_task_as_orphan(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Změna závěrů",
            conclusions="Původní bod",
        )
        task = task_service.create_task(
            title="Původní bod",
            source_module=ENTITY_MEETING,
            source_record_id=meeting.id,
            source_check_code=conclusion_check_code("Původní bod"),
        )
        meeting_service.update_meeting(
            meeting.id,
            title="Změna závěrů",
            conclusions="Nový bod",
        )
        loaded = meeting_service.get_by_id(meeting.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusions, "Nový bod")

        reloaded_task = task_service.get_task_by_id(task.id)
        assert reloaded_task is not None
        self.assertEqual(reloaded_task.title, "Původní bod")
        self.assertEqual(reloaded_task.source_module, ENTITY_MEETING)
        self.assertEqual(reloaded_task.source_record_id, meeting.id)

        view = build_conclusion_task_view(
            loaded.conclusions,
            meeting_id=meeting.id,
        )
        self.assertEqual(len(view.rows), 1)
        self.assertIsNone(view.rows[0].task)
        self.assertEqual([item.id for item in view.orphan_tasks], [task.id])

        widget = MeetingConclusionTasksWidget()
        widget.configure(
            meeting_id=meeting.id,
            get_conclusions_text=lambda: loaded.conclusions,
        )
        self.assertEqual(widget._orphan_header.text(), SECTION_LINKED_TASKS)
        self.assertFalse(widget._orphan_header.isHidden())

    def test_unsaved_meeting_blocks_task_creation(self) -> None:
        widget = MeetingConclusionTasksWidget()
        widget.configure(meeting_id=None, get_conclusions_text=lambda: "Bod")
        with patch.object(QMessageBox, "information") as info:
            widget._create_task("Bod")
        info.assert_called_once()
        self.assertEqual(info.call_args.args[2], SAVE_MEETING_BEFORE_TASK_MESSAGE)

    def test_dialog_opens_task_editor_prefilled(self) -> None:
        meeting = meeting_service.create_meeting(
            title="Prefill",
            conclusions="Připravit zápis",
        )
        created: dict = {}
        widget = MeetingConclusionTasksWidget()
        widget.configure(
            meeting_id=meeting.id,
            get_conclusions_text=lambda: "Připravit zápis",
        )

        class FakeTaskDialog:
            Accepted = 1

            def __init__(self, parent=None, task=None):
                self.title_edit = type("E", (), {"_text": ""})()
                self.title_edit.setPlainText = lambda text: setattr(
                    self.title_edit, "_text", text
                )
                self.title_edit.toPlainText = lambda: self.title_edit._text

            def exec(self):
                created["title"] = self.title_edit.toPlainText()
                return QDialogAccepted

            def get_data(self):
                return {
                    "title": self.title_edit.toPlainText(),
                    "description": "",
                    "priority": "Normální",
                    "due_date": None,
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

        QDialogAccepted = 1
        with patch(
            "moduly.schuzky.ui.meeting_conclusion_tasks_widget.TaskDialog",
            FakeTaskDialog,
        ):
            widget._create_task("Připravit zápis")

        self.assertEqual(created["title"], "Připravit zápis")
        tasks = task_service.repository.list_by_source(
            source_module=ENTITY_MEETING,
            source_record_id=meeting.id,
        )
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, "Připravit zápis")
        self.assertEqual(
            tasks[0].source_check_code,
            conclusion_check_code("Připravit zápis"),
        )

    def test_conclusions_save_unchanged(self) -> None:
        text = "Bod 1\n\nBod 2"
        meeting = meeting_service.create_meeting(
            title="Uložení závěrů",
            conclusions=text,
        )
        loaded = meeting_service.get_by_id(meeting.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusions, text)

        dialog = MeetingDialog(meeting=loaded)
        data = dialog.get_data()
        self.assertEqual(data["conclusions"], text)


if __name__ == "__main__":
    unittest.main()
