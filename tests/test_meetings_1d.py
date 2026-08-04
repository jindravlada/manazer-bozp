"""MEETINGS-1d legacy – úkoly ze závěrů nahrazeny vazbou na body (MEETINGS-2d)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

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

    from moduly.schuzky.constants import SECTION_CONCLUSION_TASKS, SECTION_LINKED_TASKS
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog


class Meetings1dLegacyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_old_meeting_level_task_sections_removed(self) -> None:
        dialog = MeetingDialog()
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        self.assertNotIn(SECTION_CONCLUSION_TASKS, labels)
        self.assertNotIn(SECTION_LINKED_TASKS, labels)
        self.assertFalse(hasattr(dialog, "conclusion_tasks"))

        with self.assertRaises(ImportError):
            importlib.import_module("moduly.schuzky.ui.meeting_conclusion_tasks_widget")


if __name__ == "__main__":
    unittest.main()
