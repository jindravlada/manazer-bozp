import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.search.ui.global_search_dialog import GlobalSearchDialog
    from core.windows.main_window import MainWindow
    from moduly.dashboard.ui.dashboard_page import DashboardPage


class DashboardSearchButtonPhase94TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_dashboard_quick_actions_do_not_contain_search_button(self) -> None:
        dashboard = DashboardPage()
        button_texts = [button.text() for button in dashboard.findChildren(QPushButton)]

        self.assertNotIn("🔎 Hledat", button_texts)
        self.assertNotIn("Hledat", button_texts)

    def test_dashboard_quick_actions_order(self) -> None:
        dashboard = DashboardPage()
        quick_buttons = [
            button.text()
            for button in dashboard.findChildren(QPushButton)
            if button.objectName() == "QuickButton"
        ]

        self.assertEqual(
            quick_buttons,
            ["+ Úraz", "Nový úkol", "Nová událost", "💾 Záloha", "♻ Obnova"],
        )

    def test_dashboard_page_has_no_open_search_callback(self) -> None:
        dashboard = DashboardPage()
        self.assertFalse(hasattr(dashboard, "open_search_callback"))


class MainWindowGlobalSearchPhase94TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def test_enter_in_toolbar_search_field_opens_global_search(self) -> None:
        self.window.search_edit.setText("bezpečnost")

        with patch.object(GlobalSearchDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window.search_edit.returnPressed.emit()

        mock_exec.assert_called_once()

    def test_global_search_button_still_opens_dialog(self) -> None:
        with patch.object(GlobalSearchDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window.global_search_button.click()

        mock_exec.assert_called_once()

    def test_main_window_has_no_focus_search_callback(self) -> None:
        self.assertFalse(hasattr(self.window, "_focus_search"))


if __name__ == "__main__":
    unittest.main()
