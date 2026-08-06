"""ŠABLONY-UX-1: sjednocení lišty editoru šablon."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
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

    from moduly.schuzky import constants as template_constants
    from moduly.schuzky.constants import (
        TEMPLATE_ACTION_DELETE,
        TEMPLATE_ACTION_EDIT,
        TEMPLATE_ACTION_NEW,
    )
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_templates_page import MeetingTemplatesPage


class SablonyUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_template(self, name: str = "Šablona A"):
        return meeting_template_service.create_template(name=name)

    def _select_rows(self, page: MeetingTemplatesPage, rows: list[int]) -> None:
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

    def test_without_selection(self) -> None:
        self._create_template()
        page = MeetingTemplatesPage()
        self.assertEqual(page._selected_row_count(), 0)
        self.assertTrue(page.new_btn.isEnabled())
        self.assertEqual(page.new_btn.text(), TEMPLATE_ACTION_NEW)
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.delete_btn.isEnabled())
        self.assertFalse(hasattr(page, "open_btn"))
        self.assertEqual(page.edit_btn.text(), TEMPLATE_ACTION_EDIT)
        self.assertEqual(page.delete_btn.text(), TEMPLATE_ACTION_DELETE)

    def test_one_selection_enables_edit_and_delete(self) -> None:
        self._create_template()
        page = MeetingTemplatesPage()
        self.assertGreaterEqual(page.table.rowCount(), 1)
        self._select_rows(page, [0])
        self.assertTrue(page.edit_btn.isEnabled())
        self.assertTrue(page.delete_btn.isEnabled())

    def test_multi_selection_disables_actions(self) -> None:
        self._create_template("Šablona 1")
        self._create_template("Šablona 2")
        page = MeetingTemplatesPage()
        self.assertEqual(
            page.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.assertGreaterEqual(page.table.rowCount(), 2)
        self._select_rows(page, [0, 1])
        self.assertEqual(page._selected_row_count(), 2)
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.delete_btn.isEnabled())

    def test_double_click_same_as_edit(self) -> None:
        init_source = inspect.getsource(MeetingTemplatesPage.__init__)
        self.assertIn("self.edit_btn.clicked.connect(self.edit_selected)", init_source)
        self.assertIn("self.table.doubleClicked.connect(self.edit_selected)", init_source)
        self.assertNotIn("open_btn", init_source)
        self.assertNotIn("open_selected", init_source)

    def test_context_menu_actions(self) -> None:
        self._create_template()
        page = MeetingTemplatesPage()
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
            patch("moduly.schuzky.ui.meeting_templates_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels, [TEMPLATE_ACTION_EDIT, TEMPLATE_ACTION_DELETE])
        self.assertEqual(enabled_flags, [True, True])

    def test_context_menu_hidden_without_selection_and_row(self) -> None:
        page = MeetingTemplatesPage()
        page.table.clearSelection()
        page._refresh_action_buttons()
        with patch("moduly.schuzky.ui.meeting_templates_page.QMenu") as menu_cls:
            page._show_table_context_menu(QPoint(-1, -1))
            menu_cls.assert_not_called()

    def test_no_select_template_dialog(self) -> None:
        self.assertFalse(hasattr(template_constants, "TEMPLATE_SELECT_MESSAGE"))
        self.assertFalse(hasattr(template_constants, "TEMPLATE_ACTION_OPEN"))
        self.assertFalse(hasattr(template_constants, "TEMPLATE_ACTION_REMOVE"))
        edit_source = inspect.getsource(MeetingTemplatesPage.edit_selected)
        delete_source = inspect.getsource(MeetingTemplatesPage.delete_selected)
        self.assertNotIn("Vyberte", edit_source)
        self.assertNotIn("Vyberte", delete_source)
        self.assertNotIn("QMessageBox.information", edit_source)
        self.assertNotIn("QMessageBox.information", delete_source)

        page = MeetingTemplatesPage()
        with patch("moduly.schuzky.ui.meeting_templates_page.QMessageBox.information") as info:
            page.edit_selected()
            page.delete_selected()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
