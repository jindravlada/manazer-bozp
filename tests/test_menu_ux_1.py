"""MENU-UX-1: zvýraznění aktivního modulu v levém menu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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

    from core.windows.main_window import MainWindow


class MenuUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dashboard_highlighted_on_startup(self) -> None:
        window = MainWindow()
        dashboard = window._sidebar_buttons["dashboard"]
        self.assertTrue(dashboard.font().bold())
        self.assertIn("#E3F2FD", dashboard.styleSheet())

        agenda = window._sidebar_buttons["agenda"]
        self.assertFalse(agenda.font().bold())
        self.assertEqual(agenda.styleSheet(), "")

    def test_switch_module_updates_highlight(self) -> None:
        window = MainWindow()
        window._show("agenda")

        dashboard = window._sidebar_buttons["dashboard"]
        agenda = window._sidebar_buttons["agenda"]

        self.assertFalse(dashboard.font().bold())
        self.assertEqual(dashboard.styleSheet(), "")
        self.assertTrue(agenda.font().bold())
        self.assertIn("#E3F2FD", agenda.styleSheet())

        window._show("nastaveni")
        settings = window._sidebar_buttons["nastaveni"]
        self.assertFalse(agenda.font().bold())
        self.assertEqual(agenda.styleSheet(), "")
        self.assertTrue(settings.font().bold())
        self.assertIn("#E3F2FD", settings.styleSheet())

    def test_button_height_unchanged(self) -> None:
        window = MainWindow()
        for button in window._sidebar_buttons.values():
            self.assertEqual(button.minimumHeight(), 34)


if __name__ == "__main__":
    unittest.main()
