import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QHideEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_table import TaskTable
    from moduly.ukoly.ui.ukoly_page import UkolyPage


class TaskTableSelectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_click_selects_row(self) -> None:
        task = task_service.create_task(title="Kontrola OOPP")
        table = TaskTable()
        table.load_tasks([task])

        table.selectRow(0)

        self.assertEqual(len(table.selectionModel().selectedRows()), 1)

    def test_clear_selection_removes_highlight(self) -> None:
        task = task_service.create_task(title="Revize hydrantů")
        table = TaskTable()
        table.load_tasks([task])
        table.selectRow(0)

        table.clear_selection()

        self.assertEqual(len(table.selectionModel().selectedRows()), 0)
        self.assertFalse(table.selectionModel().currentIndex().isValid())

    def test_click_on_empty_area_clears_selection(self) -> None:
        task = task_service.create_task(title="Školení BOZP")
        table = TaskTable()
        table.resize(800, 300)
        table.load_tasks([task])
        table.selectRow(0)

        empty_y = table.rowViewportPosition(0) + table.rowHeight(0) + 20
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPoint(40, empty_y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        table.mousePressEvent(event)

        self.assertEqual(len(table.selectionModel().selectedRows()), 0)


class UkolyPageSelectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_page(self) -> UkolyPage:
        return UkolyPage()

    def test_refresh_clears_selection(self) -> None:
        task_service.create_task(title="Doplnit dokumentaci")
        page = self._create_page()
        page.table.selectRow(0)

        page.refresh()

        self.assertEqual(len(page.table.selectionModel().selectedRows()), 0)

    def test_hide_event_clears_selection(self) -> None:
        task_service.create_task(title="Kontrola skladu")
        page = self._create_page()
        page.table.selectRow(0)

        page.hideEvent(QHideEvent())

        self.assertEqual(len(page.table.selectionModel().selectedRows()), 0)

    @patch("moduly.ukoly.ui.ukoly_page.TaskDialog")
    def test_double_click_still_opens_task(self, mock_dialog_cls) -> None:
        task = task_service.create_task(title="Oprava zábradlí XY")
        page = self._create_page()
        self._select_task_row(page, task.id)

        mock_dialog = mock_dialog_cls.return_value
        mock_dialog.exec.return_value = False

        page.edit_selected_task()

        mock_dialog_cls.assert_called_once()
        args, kwargs = mock_dialog_cls.call_args
        self.assertIsInstance(args[0], UkolyPage)
        self.assertEqual(kwargs["task"].id, task.id)

    def _select_task_row(self, page: UkolyPage, task_id: int) -> None:
        for row in range(page.table.rowCount()):
            item = page.table.item(row, 0)
            if item is not None and item.text() == str(task_id):
                page.table.selectRow(row)
                return
        self.fail(f"Task row {task_id} not found")

    def test_status_filter_still_works(self) -> None:
        task_service.create_task(title="Aktivní úkol")
        completed = task_service.create_task(title="Hotový úkol")
        task_service.mark_completed(completed.id)

        page = self._create_page()
        page.status_filter.setCurrentText("Ukončené")
        page.refresh()

        self.assertEqual(page.table.rowCount(), 1)
        self.assertIn("Hotový úkol", page.table.item(0, 2).text())


if __name__ == "__main__":
    unittest.main()
