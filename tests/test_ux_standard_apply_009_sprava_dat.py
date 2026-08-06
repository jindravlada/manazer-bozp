"""UX-STANDARD-APPLY-009: Správa dat – STANDARD 001 + 002."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton, QTreeWidgetItem

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

    from moduly.sprava_dat.sluzby.codebook_catalog_service import codebook_catalog_service
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        RegistryExportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.ui import codebooks_tab as codebooks_module
    from moduly.sprava_dat.ui import legal_registry_transfer_tab as transfer_module
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.codebooks_tab import CodebooksTab
    from moduly.sprava_dat.ui.data_quality_tab import DataQualityTab
    from moduly.sprava_dat.ui.legal_registry_diagnostics_tab import LegalRegistryDiagnosticsTab
    from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.summary_tab import SummaryTab


class UxStandardApply009SpravaDatTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def _find_tree_item(self, tree, codebook_id: str) -> QTreeWidgetItem | None:
        def walk(item: QTreeWidgetItem):
            if str(item.data(0, Qt.ItemDataRole.UserRole) or "") == codebook_id:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(tree.topLevelItemCount()):
            found = walk(tree.topLevelItem(index))
            if found is not None:
                return found
        return None

    # --- Celý modul: operace zachovány ---

    def test_page_keeps_all_tabs_and_operations(self) -> None:
        page = SpravaDatPage()
        self.assertEqual(page.tabs.count(), 6)
        self.assertIsInstance(page.summary_tab, SummaryTab)
        self.assertIsInstance(page.backup_tab, BackupTab)
        self.assertIsInstance(page.transfer_tab, LegalRegistryTransferTab)
        self.assertIsInstance(page.codebooks_tab, CodebooksTab)
        self.assertIsInstance(page.diagnostics_tab, LegalRegistryDiagnosticsTab)
        self.assertIsInstance(page.data_quality_tab, DataQualityTab)

        backup = page.backup_tab
        self.assertTrue(backup.create_mbbackup_button.isEnabled())
        self.assertTrue(backup.verify_mbbackup_button.isEnabled())
        self.assertTrue(backup.recovery_diag_button.isEnabled())

        diagnostics = page.diagnostics_tab
        self.assertTrue(diagnostics.run_button.isEnabled())
        self.assertTrue(diagnostics.run_attachment_button.isEnabled())
        self.assertTrue(diagnostics.delete_processes_button.isEnabled())

        quality = page.data_quality_tab
        self.assertTrue(quality.start_analysis_btn.isEnabled())
        self.assertEqual(quality.start_analysis_btn.text(), "Spustit analýzu")

    # --- Číselníky: výběr ---

    def test_codebooks_without_selection(self) -> None:
        tab = CodebooksTab()
        tab.catalog_tree.setCurrentItem(None)
        tab._on_catalog_selection_changed(None, None)

        self.assertIsNone(tab._selected_entry)
        self.assertIsNone(tab._selected_group)
        self.assertFalse(tab.export_button.isEnabled())
        self.assertFalse(tab.export_group_button.isEnabled())
        self.assertFalse(tab.import_group_button.isEnabled())
        self.assertTrue(tab.bulk_export_button.isEnabled())
        self.assertTrue(tab.bulk_import_button.isEnabled())
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertNotIn("Upravit", labels)
        self.assertNotIn("Otevřít", labels)

    def test_codebooks_one_selection_entry(self) -> None:
        tab = CodebooksTab()
        self.assertEqual(
            tab.catalog_tree.selectionMode(),
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        item = self._find_tree_item(tab.catalog_tree, "db:workplaces")
        self.assertIsNotNone(item)
        tab.catalog_tree.setCurrentItem(item)

        self.assertTrue(tab.export_button.isEnabled())
        self.assertFalse(tab.import_button.isHidden())
        self.assertTrue(tab.import_button.isEnabled())
        self.assertFalse(tab.export_group_button.isEnabled())
        self.assertFalse(tab.import_group_button.isEnabled())

    def test_codebooks_one_selection_group(self) -> None:
        tab = CodebooksTab()
        group_item = tab.catalog_tree.topLevelItem(0)
        self.assertIsNotNone(group_item)
        tab.catalog_tree.setCurrentItem(group_item)

        self.assertIsNotNone(tab._selected_group)
        self.assertIsNone(tab._selected_entry)
        self.assertFalse(tab.export_button.isEnabled())
        self.assertTrue(tab.export_group_button.isEnabled())

    def test_codebooks_context_menu_entry(self) -> None:
        tab = CodebooksTab()
        item = self._find_tree_item(tab.catalog_tree, "db:workplaces")
        self.assertIsNotNone(item)
        tab.catalog_tree.setCurrentItem(item)
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def isEmpty(self):
                return not labels

            def exec(self, *_args, **_kwargs):
                return None

        with (
            patch.object(tab.catalog_tree, "itemAt", return_value=item),
            patch("moduly.sprava_dat.ui.codebooks_tab.QMenu", FakeMenu),
        ):
            tab._show_catalog_context_menu(QPoint(10, 10))

        self.assertIn("Export", labels)
        self.assertIn("Import", labels)

    def test_codebooks_no_select_dialogs(self) -> None:
        source = inspect.getsource(codebooks_module)
        self.assertNotIn('"Vyberte číselník."', source)
        self.assertNotIn('"Vyberte záznam."', source)

        tab = CodebooksTab()
        tab.catalog_tree.setCurrentItem(None)
        tab._on_catalog_selection_changed(None, None)
        with patch("moduly.sprava_dat.ui.codebooks_tab.QMessageBox.information") as info:
            tab._export_selected()
            tab._import_selected()
            tab._export_group()
            tab._import_group()
            info.assert_not_called()

    # --- Přenos dat: umístění bez zbytečných dialogů ---

    def test_transfer_open_buttons_without_paths(self) -> None:
        tab = LegalRegistryTransferTab()
        self.assertFalse(tab.open_export_button.isEnabled())
        self.assertFalse(tab.open_safety_backup_button.isEnabled())
        self.assertTrue(tab.export_button.isEnabled())
        self.assertTrue(tab.import_button.isEnabled())

        source = inspect.getsource(transfer_module)
        self.assertNotIn("zatím nebyl vytvořen", source)
        self.assertNotIn("zatím nebyla vytvořena", source)

        with patch(
            "moduly.sprava_dat.ui.legal_registry_transfer_tab.QMessageBox.information"
        ) as info:
            tab._open_export_location()
            tab._open_safety_backup_location()
            info.assert_not_called()

    def test_transfer_open_export_enabled_with_path(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "apply009-export.json"
        export_path.write_text("{}", encoding="utf-8")
        data_management_settings_service.save_last_registry_export(
            RegistryExportRecord(
                created_at="2026-08-06T12:00:00",
                path=str(export_path),
                manifest={"verified": True, "record_counts": {}},
            )
        )
        tab = LegalRegistryTransferTab()
        self.assertTrue(tab.open_export_button.isEnabled())

    # --- Souhrn: Otevřít umístění podle stavu ---

    def test_summary_open_buttons_without_paths(self) -> None:
        tab = SummaryTab(navigate_callback=lambda _key: None)
        self.assertFalse(tab.open_backup_button.isEnabled())
        self.assertFalse(tab.open_restore_safety_button.isEnabled())
        self.assertFalse(tab.open_registry_button.isEnabled())
        self.assertFalse(tab.open_codebooks_button.isEnabled())

        with patch(
            "moduly.sprava_dat.ui.summary_tab.open_path_in_file_manager"
        ) as mock_open:
            tab._open_backup_location()
            tab._open_restore_safety_location()
            tab._open_registry_location()
            tab._open_codebooks_location()
            mock_open.assert_not_called()

    # --- Standard 002: žádné souběžné Otevřít/Upravit editoru ---

    def test_no_open_edit_duplicate_on_lists(self) -> None:
        for module in (codebooks_module, transfer_module):
            source = inspect.getsource(module)
            self.assertNotIn('QPushButton("Upravit")', source)
            self.assertNotIn('QPushButton("Otevřít")', source)


if __name__ == "__main__":
    unittest.main()
