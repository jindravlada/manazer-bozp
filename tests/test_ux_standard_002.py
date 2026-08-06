"""UX-STANDARD-002: sjednocení akcí Otevřít a Upravit (Agenda)."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton

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

    from moduly.agenda import constants as agenda_constants
    from moduly.agenda.constants import ACTION_EDIT
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.ukoly.sluzby.task_service import task_service


class UxStandard002TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_agenda_has_only_edit_not_open(self) -> None:
        task_service.create_task(
            title="Úkol UX-002",
            due_date=date.today() + timedelta(days=1),
        )
        page = AgendaPage()
        self.assertEqual(page.edit_btn.text(), ACTION_EDIT)
        self.assertIsInstance(page.edit_btn, QPushButton)
        self.assertFalse(hasattr(page, "open_btn"))
        self.assertFalse(hasattr(agenda_constants, "ACTION_OPEN"))

        toolbar_labels = [
            btn.text()
            for btn in page.findChildren(QPushButton)
            if btn.text() in ("Otevřít", ACTION_EDIT)
        ]
        self.assertEqual(toolbar_labels.count(ACTION_EDIT), 1)
        self.assertNotIn("Otevřít", toolbar_labels)

    def test_double_click_uses_edit_selected(self) -> None:
        init_source = inspect.getsource(AgendaPage.__init__)
        self.assertIn("self.edit_btn.clicked.connect(self.edit_selected)", init_source)
        self.assertIn("self.table.doubleClicked.connect(self.edit_selected)", init_source)

    def test_edit_activation_follows_standard_001(self) -> None:
        task_service.create_task(
            title="Úkol aktivace",
            due_date=date.today() + timedelta(days=1),
        )
        page = AgendaPage()
        self.assertFalse(page.edit_btn.isEnabled())
        page.table.selectRow(0)
        page._refresh_action_buttons()
        self.assertTrue(page.edit_btn.isEnabled())
        page.table.clear_selection()
        page._refresh_action_buttons()
        self.assertFalse(page.edit_btn.isEnabled())

    def test_standard_001_documents_open_edit_rule(self) -> None:
        path = Path(__file__).resolve().parents[1] / "UX_STANDARD_001.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("Nepoužívat současně", text)
        self.assertIn("Otevřít", text)
        self.assertIn("Upravit", text)
        self.assertIn("stejný editor", text)


if __name__ == "__main__":
    unittest.main()
