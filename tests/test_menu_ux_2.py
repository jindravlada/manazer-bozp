"""MENU-UX-2: výraznější zvýraznění aktivního modulu."""

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
    return (
        button.font().bold()
        and "#E3F2FD" in sheet
        and "2px solid #93c5fd" in sheet
    )


class MenuUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _highlighted_keys(self, window: MainWindow) -> list[str]:
        return [
            key
            for key, button in window._sidebar_buttons.items()
            if _is_highlighted(button)
        ]

    def test_active_style_has_bold_background_and_border(self) -> None:
        window = MainWindow()
        self.assertEqual(
            window._SIDEBAR_ACTIVE_STYLE,
            "QPushButton { background-color: #E3F2FD; border: 2px solid #93c5fd; }",
        )
        self.assertEqual(self._highlighted_keys(window), ["dashboard"])

    def test_switch_moves_highlight_to_single_module(self) -> None:
        window = MainWindow()
        for key in ("agenda", "kniha_urazu", "nastaveni", "dashboard"):
            window._show(key)
            highlighted = self._highlighted_keys(window)
            self.assertEqual(highlighted, [key])
            self.assertEqual(len(highlighted), 1)

            for other_key, button in window._sidebar_buttons.items():
                if other_key == key:
                    continue
                self.assertFalse(button.font().bold())
                self.assertEqual(button.styleSheet(), "")

    def test_button_height_unchanged(self) -> None:
        window = MainWindow()
        for button in window._sidebar_buttons.values():
            self.assertEqual(button.minimumHeight(), 34)


if __name__ == "__main__":
    unittest.main()
