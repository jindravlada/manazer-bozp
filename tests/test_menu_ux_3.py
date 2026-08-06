"""MENU-UX-3: odstranění tučného písma aktivního modulu."""

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


def _is_highlighted(button) -> bool:
    sheet = button.styleSheet()
    return "#E3F2FD" in sheet and "2px solid #93c5fd" in sheet


class MenuUx3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _highlighted_keys(self, window: MainWindow) -> list[str]:
        return [
            key
            for key, button in window._sidebar_buttons.items()
            if _is_highlighted(button)
        ]

    def test_no_bold_on_active_module(self) -> None:
        window = MainWindow()
        for button in window._sidebar_buttons.values():
            self.assertFalse(button.font().bold())

        dashboard = window._sidebar_buttons["dashboard"]
        self.assertTrue(_is_highlighted(dashboard))
        self.assertNotIn("font-weight", dashboard.styleSheet().lower())
        self.assertNotIn("bold", dashboard.styleSheet().lower())

    def test_all_modules_highlight_immediately_and_exclusively(self) -> None:
        window = MainWindow()
        keys = list(window._sidebar_buttons.keys())
        self.assertGreaterEqual(len(keys), 5)

        for key in keys:
            window._show(key)
            highlighted = self._highlighted_keys(window)
            self.assertEqual(
                highlighted,
                [key],
                f"Po přepnutí na {key} má být zvýrazněn pouze aktivní modul",
            )
            for other_key, button in window._sidebar_buttons.items():
                self.assertFalse(button.font().bold())
                if other_key == key:
                    self.assertTrue(_is_highlighted(button))
                else:
                    self.assertEqual(button.styleSheet(), "")


if __name__ == "__main__":
    unittest.main()
