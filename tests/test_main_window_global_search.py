import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.search import global_search_service
    from core.search.ui.global_search_dialog import GlobalSearchDialog
    from core.windows.main_window import MainWindow
    from moduly.ukoly.sluzby.task_service import task_service


class MainWindowGlobalSearchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def test_toolbar_has_global_search_button(self) -> None:
        self.assertEqual(self.window.global_search_button.text(), "Globální vyhledávání")

    def test_ctrl_k_opens_global_search_dialog(self) -> None:
        with patch.object(GlobalSearchDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window._global_search_shortcut.activated.emit()

        mock_exec.assert_called_once()

    def test_button_opens_global_search_dialog(self) -> None:
        with patch.object(GlobalSearchDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window.global_search_button.click()

        mock_exec.assert_called_once()

    def test_dialog_created_with_service_and_host(self) -> None:
        with patch("core.windows.main_window.GlobalSearchDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window._open_global_search_dialog()

        mock_dialog_cls.assert_called_once_with(
            parent=self.window,
            search_service=global_search_service,
            host=self.window,
            initial_query="",
        )

    def test_dialog_has_focus_in_search_field(self) -> None:
        dialog = GlobalSearchDialog(parent=self.window, host=self.window)
        dialog.show()
        QApplication.processEvents()

        self.assertTrue(dialog._search_edit.hasFocus())
        dialog.close()

    def test_opening_result_from_dialog_works(self) -> None:
        task = task_service.create_task(title="Integrace globálního vyhledávání")
        dialog = GlobalSearchDialog(
            parent=self.window,
            host=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("integrace")

        match = next(item for item in dialog.result_items() if item.entity_id == task.id)
        ukoly_page = self.window._page_widgets["ukoly"]

        with patch.object(ukoly_page, "open_task") as mock_open_task:
            dialog._open_result(match)

        mock_open_task.assert_called_once_with(task.id)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_esc_closes_dialog(self) -> None:
        dialog = GlobalSearchDialog(parent=self.window, host=self.window)
        dialog.show()
        QApplication.processEvents()

        dialog.keyPressEvent(
            QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            )
        )

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)


if __name__ == "__main__":
    unittest.main()
