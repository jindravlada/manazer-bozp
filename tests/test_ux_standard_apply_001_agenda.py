"""UX-STANDARD-APPLY-001: Agenda – aktivace akcí podle výběru."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QItemSelectionModel, QPoint
from PySide6.QtWidgets import QAbstractItemView, QApplication

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
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


class UxStandardApply001AgendaTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_task(self, title: str = "Úkol A"):
        return task_service.create_task(
            title=title,
            due_date=date.today() + timedelta(days=2),
        )

    def _create_meeting(self, title: str = "Událost A"):
        return meeting_service.create_meeting(
            title=title,
            starts_at=datetime.now() + timedelta(days=1),
            status=STATUS_PLANNED,
        )

    def _select_rows(self, page: AgendaPage, rows: list[int]) -> None:
        model = page.table.selectionModel()
        model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        for row in rows:
            index = page.table.model().index(row, 0)
            model.select(index, flags)
        page._refresh_action_buttons()

    def test_open_agenda_without_selection(self) -> None:
        self._create_task()
        page = AgendaPage()
        self.assertEqual(page._selected_row_count(), 0)
        self.assertTrue(page.new_task_btn.isEnabled())
        self.assertTrue(page.new_meeting_btn.isEnabled())
        self.assertTrue(page.templates_btn.isEnabled())
        self.assertTrue(page.new_from_template_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(hasattr(page, "open_btn"))

    def test_one_selection_enables_edit(self) -> None:
        self._create_task()
        page = AgendaPage()
        self.assertGreaterEqual(page.table.rowCount(), 1)
        self._select_rows(page, [0])
        self.assertTrue(page.edit_btn.isEnabled())

    def test_multi_selection_disables_edit(self) -> None:
        self._create_task("Úkol 1")
        self._create_meeting("Událost 1")
        page = AgendaPage()
        self.assertEqual(
            page.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.assertGreaterEqual(page.table.rowCount(), 2)
        self._select_rows(page, [0, 1])
        self.assertEqual(page._selected_row_count(), 2)
        self.assertFalse(page.edit_btn.isEnabled())

    def test_clear_selection_disables_edit(self) -> None:
        self._create_task()
        page = AgendaPage()
        self._select_rows(page, [0])
        page.table.clear_selection()
        page._refresh_action_buttons()
        self.assertFalse(page.edit_btn.isEnabled())

    def test_double_click_same_as_edit(self) -> None:
        init_source = inspect.getsource(AgendaPage.__init__)
        self.assertIn("self.edit_btn.clicked.connect(self.edit_selected)", init_source)
        self.assertIn("self.table.doubleClicked.connect(self.edit_selected)", init_source)
        self.assertNotIn("open_btn", init_source)

    def test_context_menu_enables_edit_for_one_row(self) -> None:
        self._create_task()
        page = AgendaPage()
        enabled_flags: list[bool] = []
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()

                def set_enabled(value: bool) -> None:
                    enabled_flags.append(value)

                action.setEnabled = set_enabled
                return action

            def exec(self, *_args, **_kwargs):
                return None

        page.table.selectRow(0)
        page._refresh_action_buttons()
        with (
            patch.object(page.table, "indexAt", return_value=page.table.model().index(0, 0)),
            patch("moduly.agenda.ui.agenda_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels, [ACTION_EDIT])
        self.assertEqual(enabled_flags, [True])

    def test_context_menu_hidden_without_selection_and_row(self) -> None:
        page = AgendaPage()
        page.table.clear_selection()
        page._refresh_action_buttons()
        with patch("moduly.agenda.ui.agenda_page.QMenu") as menu_cls:
            page._show_table_context_menu(QPoint(-1, -1))
            menu_cls.assert_not_called()

    def test_no_select_item_dialog(self) -> None:
        self.assertFalse(hasattr(agenda_constants, "SELECT_ITEM_MESSAGE"))
        source = inspect.getsource(AgendaPage.edit_selected)
        self.assertNotIn("Vyberte", source)
        self.assertNotIn("QMessageBox.information", source)

        page = AgendaPage()
        with patch("moduly.agenda.ui.agenda_page.QMessageBox.information") as info:
            page.edit_selected()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
