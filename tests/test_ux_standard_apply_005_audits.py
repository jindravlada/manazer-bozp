"""UX-STANDARD-APPLY-005: Audity systému řízení – STANDARD 001 + 002."""

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

    from moduly.audity.constants import (
        AUDIT_DETAILED_REPORT_BUTTON_LABEL,
        AUDIT_PROTOCOL_BUTTON_LABEL,
        AUDIT_STATUS_FILTER_VSE,
        YEAR_FILTER_VSE,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui import audity_page as page_module
    from moduly.audity.ui.audity_page import AudityPage


class UxStandardApply005AuditsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def _prepare_page(self) -> AudityPage:
        page = AudityPage()
        page.status_filter.setCurrentText(AUDIT_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        return page

    def _select_rows(self, page: AudityPage, rows: list[int]) -> None:
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
        audit_service.create_audit(title="Audit A")
        page = self._prepare_page()
        self.assertEqual(page._selected_row_count(), 0)
        self.assertTrue(page.new_btn.isEnabled())
        self.assertTrue(page.program_btn.isEnabled())
        self.assertTrue(page.refresh_btn.isEnabled())
        self.assertTrue(page.knowledge_editor_btn.isEnabled())
        self.assertTrue(page.report_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.delete_btn.isEnabled())
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())
        labels = [btn.text() for btn in page.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(page.edit_btn.text(), "Upravit")

    def test_one_selection_enables_edit_delete(self) -> None:
        audit_service.create_audit(title="Audit B", started_at=date(2026, 3, 1))
        page = self._prepare_page()
        self.assertGreaterEqual(page.table.rowCount(), 1)
        self._select_rows(page, [0])
        self.assertTrue(page.edit_btn.isEnabled())
        self.assertTrue(page.delete_btn.isEnabled())

    def test_multi_selection_disables_single_actions(self) -> None:
        audit_service.create_audit(title="Audit 1", started_at=date(2026, 3, 1))
        audit_service.create_audit(title="Audit 2", started_at=date(2026, 3, 2))
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
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

    def test_double_click_is_edit(self) -> None:
        init_source = inspect.getsource(AudityPage.__init__)
        self.assertIn("self.edit_btn.clicked.connect(self.open_selected_audit)", init_source)
        self.assertIn(
            "self.table.doubleClicked.connect(self.open_selected_audit)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

    def test_context_menu(self) -> None:
        audit_service.create_audit(
            title="Dokončený",
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )
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

            def addSeparator(self):
                return None

            def exec(self, *_args, **_kwargs):
                return None

        page.table.selectRow(0)
        page._refresh_action_buttons()
        with (
            patch.object(page.table, "indexAt", return_value=page.table.model().index(0, 0)),
            patch("moduly.audity.ui.audity_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertEqual(labels[1], "Smazat")
        self.assertIn(AUDIT_PROTOCOL_BUTTON_LABEL, labels)
        self.assertIn(AUDIT_DETAILED_REPORT_BUTTON_LABEL, labels)
        self.assertTrue(all(enabled_flags[:2]))

    def test_no_select_audit_dialogs(self) -> None:
        source = inspect.getsource(page_module)
        self.assertNotIn('"Vyberte audit."', source)

        page = self._prepare_page()
        with patch("moduly.audity.ui.audity_page.QMessageBox.information") as info:
            page.open_selected_audit()
            page.delete_selected_audit()
            page.export_selected_protocol()
            page.export_selected_detailed_report()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
