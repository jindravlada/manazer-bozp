"""UX-STANDARD-APPLY-004: Vyšetřování MU – STANDARD 001 + 002."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QItemSelectionModel, QPoint
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton

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

    from moduly.vysetrovani_mu.constants import MU_STATUS_FILTER_VSE, YEAR_FILTER_VSE
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import (
        mu_investigation_service,
    )
    from moduly.vysetrovani_mu.ui import vysetrovani_mu_page as page_module
    from moduly.vysetrovani_mu.ui.vysetrovani_mu_page import VysetrovaniMuPage


class UxStandardApply004MuTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        # Filtr Vše / Vše, ať jsou nové záznamy vždy vidět.
        pass

    def _create_investigation(self, title: str = "MU A"):
        return mu_investigation_service.create_investigation(
            title=title,
            started_at=date.today(),
        )

    def _prepare_page(self) -> VysetrovaniMuPage:
        page = VysetrovaniMuPage()
        page.status_filter.setCurrentText(MU_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(
            page.year_filter.findData(YEAR_FILTER_VSE)
        )
        page.refresh()
        return page

    def _selection_buttons(self, page: VysetrovaniMuPage):
        return (page.edit_btn, page.delete_btn)

    def _select_rows(self, page: VysetrovaniMuPage, rows: list[int]) -> None:
        model = page.table.selectionModel()
        model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        for row in rows:
            model.select(page.table.model().index(row, 0), flags)
        page._refresh_action_buttons()

    def test_without_selection(self) -> None:
        self._create_investigation()
        page = self._prepare_page()
        self.assertEqual(page._selected_row_count(), 0)
        self.assertTrue(page.new_btn.isEnabled())
        self.assertTrue(page.sedmero_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())
        labels = [btn.text() for btn in page.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(page.edit_btn.text(), "Upravit")

    def test_one_selection_enables_edit_delete(self) -> None:
        self._create_investigation()
        page = self._prepare_page()
        self.assertGreaterEqual(page.table.rowCount(), 1)
        self._select_rows(page, [0])
        self.assertTrue(page.edit_btn.isEnabled())
        self.assertTrue(page.delete_btn.isEnabled())
        self.assertTrue(page.new_btn.isEnabled())
        self.assertTrue(page.sedmero_btn.isEnabled())

    def test_multi_selection_disables_single_actions(self) -> None:
        self._create_investigation("MU 1")
        self._create_investigation("MU 2")
        page = self._prepare_page()
        self.assertEqual(
            page.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.assertGreaterEqual(page.table.rowCount(), 2)
        self._select_rows(page, [0, 1])
        self.assertEqual(page._selected_row_count(), 2)
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.delete_btn.isEnabled())

    def test_double_click_is_edit(self) -> None:
        init_source = inspect.getsource(VysetrovaniMuPage.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_investigation)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_investigation)",
            init_source,
        )
        self.assertNotIn("Otevřít", init_source)

    def test_context_menu(self) -> None:
        self._create_investigation()
        page = self._prepare_page()
        labels: list[str] = []
        enabled_flags: list[bool] = []

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
            patch("moduly.vysetrovani_mu.ui.vysetrovani_mu_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels, ["Upravit", "Smazat"])
        self.assertEqual(enabled_flags, [True, True])

    def test_no_select_dialogs(self) -> None:
        source = inspect.getsource(page_module)
        self.assertNotIn("Vyberte vyšetřování.", source)

        page = self._prepare_page()
        with patch(
            "moduly.vysetrovani_mu.ui.vysetrovani_mu_page.QMessageBox.information"
        ) as info:
            page.edit_selected_investigation()
            page.delete_selected_investigation()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
