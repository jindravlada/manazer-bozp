"""UX-STANDARD-APPLY-003: Kniha úrazů – dokončení STANDARD 001 + 002."""

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

    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui import kniha_urazu_page as page_module
    from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage


class UxStandardApply003AccidentsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self, name: str = "Jan Novák"):
        return accident_service.create_accident(
            jmeno_prijmeni=name,
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            accident_date=date(2026, 4, 1),
            accident_time="10:00",
            popis_urazoveho_deje="Pád",
        )

    def _selection_buttons(self, page: KnihaUrazuPage):
        return (
            page.edit_btn,
            page.notice_btn,
            page.investigation_btn,
            page.mu_investigation_btn,
            page.vypis_btn,
            page.final_report_btn,
        )

    def _select_rows(self, page: KnihaUrazuPage, rows: list[int]) -> None:
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

    def test_toolbar_without_selection(self) -> None:
        self._create_accident()
        page = KnihaUrazuPage()
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())
        labels = [btn.text() for btn in page.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(page.edit_btn.text(), "Upravit")

    def test_one_selection_enables_all_record_actions(self) -> None:
        accident = self._create_accident()
        page = KnihaUrazuPage()
        self.assertTrue(page._select_accident(accident.id))
        page._refresh_action_buttons()
        for button in self._selection_buttons(page):
            self.assertTrue(button.isEnabled(), button.text())

    def test_multi_selection_disables_record_actions(self) -> None:
        self._create_accident("A")
        self._create_accident("B")
        page = KnihaUrazuPage()
        self.assertEqual(
            page.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.assertGreaterEqual(page.table.rowCount(), 2)
        self._select_rows(page, [0, 1])
        self.assertEqual(page._selected_row_count(), 2)
        self.assertTrue(page.new_btn.isEnabled())
        for button in self._selection_buttons(page):
            self.assertFalse(button.isEnabled(), button.text())

    def test_double_click_is_edit(self) -> None:
        init_source = inspect.getsource(KnihaUrazuPage.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_accident)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_accident)",
            init_source,
        )
        self.assertNotIn("Otevřít", init_source)

    def test_context_menu_mirrors_toolbar(self) -> None:
        self._create_accident()
        page = KnihaUrazuPage()
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
        expected = [btn.text() for btn in self._selection_buttons(page)]
        with (
            patch.object(page.table, "indexAt", return_value=page.table.model().index(0, 0)),
            patch("moduly.kniha_urazu.ui.kniha_urazu_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels, expected)
        self.assertEqual(enabled_flags, [True] * len(expected))

    def test_no_select_accident_dialogs(self) -> None:
        source = inspect.getsource(page_module)
        self.assertNotIn("Vyberte úraz.", source)

        page = KnihaUrazuPage()
        with patch("moduly.kniha_urazu.ui.kniha_urazu_page.QMessageBox.information") as info:
            page.edit_selected_accident()
            page.open_union_notice()
            page.generate_accident_report()
            page.generate_final_report()
            page.open_investigation()
            page.open_mu_investigation()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
