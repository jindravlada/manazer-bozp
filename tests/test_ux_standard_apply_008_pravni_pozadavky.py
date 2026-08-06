"""UX-STANDARD-APPLY-008: Právní požadavky – STANDARD 001 + 002."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
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

    from moduly.pravni_pozadavky.constants import (
        CHANGE_UPDATED,
        DOCUMENT_TYPE_VYHLASKA,
        FILTER_ALL_RECORDS,
    )
    from moduly.pravni_pozadavky.modely.legal_change import LegalChange
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.ui import pravni_pozadavky_requirements_tab as req_module
    from moduly.pravni_pozadavky.ui import pravni_predpisy_tab as docs_module
    from moduly.pravni_pozadavky.ui import zmeny_legislativy_tab as changes_module
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab import (
        PravniPozadavkyRequirementsTab,
    )
    from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab
    from moduly.pravni_pozadavky.ui.zmeny_legislativy_tab import ZmenyLegislativyTab


class UxStandardApply008PravniPozadavkyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(LegalChange))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

    def _select_rows(self, table, rows: list[int], refresh_cb) -> None:
        model = table.selectionModel()
        model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        for row in rows:
            model.select(table.model().index(row, 0), flags)
        refresh_cb()

    # --- Řídicí procesy ---

    def _prepare_requirements(self) -> PravniPozadavkyRequirementsTab:
        tab = PravniPozadavkyRequirementsTab()
        tab.active_filter.setCurrentText(FILTER_ALL_RECORDS)
        tab.refresh()
        return tab

    def test_requirements_without_selection(self) -> None:
        legal_requirement_service.create_requirement(title="Proces A")
        tab = self._prepare_requirements()
        self.assertEqual(tab._selected_row_count(), 0)
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertTrue(tab.import_json_btn.isEnabled())
        self.assertTrue(tab.merge_btn.isEnabled())
        self.assertTrue(tab.diagnostic_registry_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.archive_btn.isEnabled())
        self.assertFalse(tab.verify_btn.isEnabled())
        self.assertFalse(tab.task_btn.isEnabled())
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(tab.edit_btn.text(), "Upravit")

    def test_requirements_one_and_multi_selection(self) -> None:
        legal_requirement_service.create_requirement(title="Proces 1")
        legal_requirement_service.create_requirement(title="Proces 2")
        tab = self._prepare_requirements()
        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.archive_btn.isEnabled())
        self.assertTrue(tab.verify_btn.isEnabled())

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertEqual(tab._selected_row_count(), 2)
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.archive_btn.isEnabled())
        self.assertFalse(tab.verify_btn.isEnabled())
        self.assertFalse(tab.task_btn.isEnabled())

    def test_requirements_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(PravniPozadavkyRequirementsTab.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_requirement)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_requirement)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

        legal_requirement_service.create_requirement(title="Proces menu")
        tab = self._prepare_requirements()
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def exec(self, *_args, **_kwargs):
                return None

        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        with (
            patch.object(tab.table, "indexAt", return_value=tab.table.model().index(0, 0)),
            patch(
                "moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab.QMenu",
                FakeMenu,
            ),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertIn("Archivovat", labels)
        self.assertIn("Ověřit plnění", labels)

    def test_requirements_no_select_dialogs(self) -> None:
        source = inspect.getsource(req_module)
        self.assertNotIn('"Vyberte požadavek."', source)

        tab = self._prepare_requirements()
        with patch(
            "moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab.QMessageBox.information"
        ) as info:
            tab.edit_selected_requirement()
            tab.archive_selected_requirement()
            tab.verify_selected_requirement()
            tab.create_task_for_selected()
            info.assert_not_called()

    # --- Právní předpisy ---

    def _prepare_documents(self) -> PravniPredpisyTab:
        tab = PravniPredpisyTab()
        tab.active_filter.setCurrentText(FILTER_ALL_RECORDS)
        tab.refresh()
        return tab

    def test_documents_without_selection(self) -> None:
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška A",
            number="1",
            year=2026,
        )
        tab = self._prepare_documents()
        self.assertEqual(tab._selected_row_count(), 0)
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertTrue(tab.import_btn.isEnabled())
        self.assertTrue(tab.import_txt_btn.isEnabled())
        self.assertTrue(tab.import_bulk_internet_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.valid_text_btn.isEnabled())
        self.assertFalse(tab.export_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(tab.edit_btn.text(), "Upravit")

    def test_documents_one_and_multi_selection(self) -> None:
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Doc 1",
            number="1",
            year=2026,
        )
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Doc 2",
            number="2",
            year=2026,
        )
        tab = self._prepare_documents()
        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.valid_text_btn.isEnabled())
        self.assertTrue(tab.export_btn.isEnabled())
        self.assertTrue(tab.toggle_btn.isEnabled())

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertEqual(tab._selected_row_count(), 2)
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.valid_text_btn.isEnabled())
        self.assertFalse(tab.export_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())

    def test_documents_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(PravniPredpisyTab.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_document)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_document)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

        legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Doc menu",
            number="3",
            year=2026,
        )
        tab = self._prepare_documents()
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def exec(self, *_args, **_kwargs):
                return None

        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        with (
            patch.object(tab.table, "indexAt", return_value=tab.table.model().index(0, 0)),
            patch("moduly.pravni_pozadavky.ui.pravni_predpisy_tab.QMenu", FakeMenu),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertIn("Platné znění", labels)
        self.assertIn("Export JSON", labels)

    def test_documents_no_select_dialogs(self) -> None:
        source = inspect.getsource(docs_module)
        self.assertNotIn('"Vyberte právní předpis."', source)

        tab = self._prepare_documents()
        with patch(
            "moduly.pravni_pozadavky.ui.pravni_predpisy_tab.QMessageBox.information"
        ) as info:
            tab.edit_selected_document()
            tab.open_valid_text()
            tab.export_json_document()
            tab.toggle_selected_document()
            info.assert_not_called()

    # --- Zjištěné změny ---

    def _create_change(self, *, title: str = "Změna"):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title=f"Předpis pro {title}",
            number="10",
            year=2026,
        )
        return legal_change_service.create(
            legal_document_id=document.id,
            change_type=CHANGE_UPDATED,
            title=title,
        )

    def test_changes_without_selection(self) -> None:
        self._create_change(title="Změna A")
        tab = ZmenyLegislativyTab()
        self.assertEqual(tab._selected_row_count(), 0)
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())
        self.assertFalse(tab.evaluate_btn.isEnabled())

    def test_changes_one_and_multi_selection(self) -> None:
        self._create_change(title="Z1")
        self._create_change(title="Z2")
        tab = ZmenyLegislativyTab()
        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.open_btn.isEnabled())
        self.assertTrue(tab.toggle_btn.isEnabled())
        self.assertTrue(tab.evaluate_btn.isEnabled())

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertEqual(tab._selected_row_count(), 2)
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())
        self.assertFalse(tab.evaluate_btn.isEnabled())

    def test_changes_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(ZmenyLegislativyTab.__init__)
        self.assertIn(
            "self.open_btn.clicked.connect(self.open_selected_change)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.open_selected_change)",
            init_source,
        )

        self._create_change(title="Změna menu")
        tab = ZmenyLegislativyTab()
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def exec(self, *_args, **_kwargs):
                return None

        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        with (
            patch.object(tab.table, "indexAt", return_value=tab.table.model().index(0, 0)),
            patch("moduly.pravni_pozadavky.ui.zmeny_legislativy_tab.QMenu", FakeMenu),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Otevřít")
        self.assertIn("Deaktivovat", labels)
        self.assertIn("Označit jako vyhodnocené", labels)

    def test_changes_no_select_dialogs(self) -> None:
        source = inspect.getsource(changes_module)
        self.assertNotIn('"Vyberte změnu."', source)

        tab = ZmenyLegislativyTab()
        with patch(
            "moduly.pravni_pozadavky.ui.zmeny_legislativy_tab.QMessageBox.information"
        ) as info:
            tab.open_selected_change()
            tab.toggle_selected_change()
            tab.mark_selected_evaluated()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
