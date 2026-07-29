import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    from core.search.constants import ENTITY_TYPE_LEGAL_REQUIREMENT
    from core.search.global_search_result import GlobalSearchResult
    from core.search.ui.global_search_dialog import GlobalSearchDialog
    from core.windows.main_window import MainWindow
    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_ZAKON
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
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

    def test_dialog_created_with_service(self) -> None:
        with patch("core.windows.main_window.GlobalSearchDialog") as mock_dialog_cls:
            mock_dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window._open_global_search_dialog()

        mock_dialog_cls.assert_called_once_with(
            parent=self.window,
            search_service=global_search_service,
            initial_query="",
        )

    def test_dialog_has_focus_in_search_field(self) -> None:
        dialog = GlobalSearchDialog(parent=self.window)
        dialog.show()
        QApplication.processEvents()

        self.assertTrue(dialog._search_edit.hasFocus())
        dialog.close()

    def test_opening_task_after_dialog_closes(self) -> None:
        task = task_service.create_task(title="Integrace globálního vyhledávání")
        dialog = GlobalSearchDialog(
            parent=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("integrace")

        match = next(item for item in dialog.result_items() if item.entity_id == task.id)
        ukoly_page = self.window._page_widgets["ukoly"]

        with patch.object(ukoly_page, "open_task") as mock_open_task:
            dialog._accept_result(match)
            self.assertFalse(dialog.isVisible())
            self.window._open_global_search_result(match)

        mock_open_task.assert_called_once_with(task.id)

    def test_opening_legal_requirement_after_dialog_closes(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-087",
            requirement_summary="Hodnocení rizik",
        )
        dialog = GlobalSearchDialog(
            parent=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("P-087")

        match = next(item for item in dialog.result_items() if item.entity_id == requirement.id)
        pravni_page = self.window._page_widgets["pravni_pozadavky"]

        with patch.object(pravni_page, "open_requirement") as mock_open:
            dialog._accept_result(match)
            self.assertFalse(dialog.isVisible())
            self.window._open_global_search_result(match)

        mock_open.assert_called_once_with(requirement.id)

    def test_opening_legal_document_after_dialog_closes(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Vyhláška bezpečnosti práce",
            number="500/2026",
            year=2026,
            short_title="VBP",
        )
        dialog = GlobalSearchDialog(
            parent=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("500/2026")

        match = next(item for item in dialog.result_items() if item.entity_id == document.id)
        pravni_page = self.window._page_widgets["pravni_pozadavky"]

        with patch.object(pravni_page, "open_document") as mock_open:
            dialog._accept_result(match)
            self.assertFalse(dialog.isVisible())
            self.window._open_global_search_result(match)

        mock_open.assert_called_once_with(document.id)

    def test_enter_opens_result_only_after_dialog_closes(self) -> None:
        task = task_service.create_task(title="Enter test globálního vyhledávání")
        dialog = GlobalSearchDialog(
            parent=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("enter test")
        item = next(
            row_item
            for row in range(dialog._results_list.count())
            if (row_item := dialog._results_list.item(row)) is not None
            and isinstance(row_item.data(Qt.ItemDataRole.UserRole), GlobalSearchResult)
            and row_item.data(Qt.ItemDataRole.UserRole).entity_id == task.id
        )
        dialog._results_list.setCurrentItem(item)

        ukoly_page = self.window._page_widgets["ukoly"]
        with patch.object(ukoly_page, "open_task") as mock_open_task:
            dialog._open_selected_result()
            self.assertFalse(dialog.isVisible())
            self.assertIsNotNone(dialog.selected_result)
            self.window._open_global_search_result(dialog.selected_result)

        mock_open_task.assert_called_once_with(task.id)

    def test_double_click_opens_result_only_after_dialog_closes(self) -> None:
        task = task_service.create_task(title="Dvojklik globálního vyhledávání")
        dialog = GlobalSearchDialog(
            parent=self.window,
            search_service=global_search_service,
        )
        dialog._search_edit.setText("dvojklik")
        item = next(
            row_item
            for row in range(dialog._results_list.count())
            if (row_item := dialog._results_list.item(row)) is not None
            and isinstance(row_item.data(Qt.ItemDataRole.UserRole), GlobalSearchResult)
            and row_item.data(Qt.ItemDataRole.UserRole).entity_id == task.id
        )

        ukoly_page = self.window._page_widgets["ukoly"]
        with patch.object(ukoly_page, "open_task") as mock_open_task:
            dialog._on_result_item_activated(item)
            self.assertFalse(dialog.isVisible())
            self.window._open_global_search_result(dialog.selected_result)

        mock_open_task.assert_called_once_with(task.id)

    def test_open_global_search_dialog_opens_result_after_exec(self) -> None:
        result = GlobalSearchResult(
            entity_type=ENTITY_TYPE_LEGAL_REQUIREMENT,
            entity_id=42,
            title="Test",
            module_key="pravni_pozadavky",
            group_label="Procesy",
        )
        dialog_mock = MagicMock()
        dialog_mock.exec.return_value = QDialog.DialogCode.Accepted
        dialog_mock.selected_result = result

        with patch("core.windows.main_window.GlobalSearchDialog", return_value=dialog_mock):
            with patch.object(self.window, "_open_global_search_result") as mock_open:
                self.window._open_global_search_dialog()

        mock_open.assert_called_once_with(result)

    def test_open_failure_shows_status_message(self) -> None:
        result = GlobalSearchResult(
            entity_type="unknown",
            entity_id=1,
            title="Neznámý",
            module_key="x",
            group_label="X",
        )

        with patch.object(global_search_service, "open_result", return_value=False):
            self.window._open_global_search_result(result)

        self.assertEqual(
            self.window.statusBar().currentMessage(),
            "Globální vyhledávání: výsledek nelze otevřít",
        )

    def test_esc_closes_dialog(self) -> None:
        dialog = GlobalSearchDialog(parent=self.window)
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
