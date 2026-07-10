import importlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby.codebook_catalog_service import (
        MODULE_PROVERKY,
        codebook_catalog_service,
    )
    from moduly.sprava_dat.sluzby.codebook_export_service import codebook_export_service
    from moduly.sprava_dat.sluzby.codebook_manifest_service import MANIFEST_FILENAME
    from moduly.sprava_dat.sluzby.codebook_transfer_service import codebook_transfer_service
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.codebooks_tab import CodebooksTab
    from moduly.sprava_dat.ui.legal_registry_transfer_tab import LegalRegistryTransferTab
    from moduly.sprava_dat.ui.summary_tab import SummaryTab


def _collect_visible_text(widget) -> str:
    return "\n".join(label.text() for label in widget.findChildren(QLabel))


class SpravaDatTerminologyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_ui_texts_do_not_use_manifest_word(self) -> None:
        tabs = [BackupTab(), LegalRegistryTransferTab(), CodebooksTab(), SummaryTab(lambda _k: None)]
        for tab in tabs:
            tab.show()
            self._app.processEvents()
            text = _collect_visible_text(tab)
            self.assertNotIn("Manifest", text, msg=tab.__class__.__name__)


class SummaryLayoutTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_backup_and_restore_sections_are_side_by_side(self) -> None:
        tab = SummaryTab(navigate_callback=lambda _k: None)
        tab.show()
        self._app.processEvents()

        group_titles = [group.title() for group in tab.findChildren(QGroupBox)]
        self.assertIn("Kompletní záloha", group_titles)
        self.assertIn("Obnova kompletní zálohy", group_titles)

        row = tab.findChild(QWidget, "summaryBackupRestoreRow")
        self.assertIsNotNone(row)
        layout = row.layout()
        self.assertIsNotNone(layout)
        self.assertIsInstance(layout, QHBoxLayout)
        self.assertEqual(layout.count(), 2)


class LegalRegistryTransferLayoutTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_controls_appear_before_explanation(self) -> None:
        tab = LegalRegistryTransferTab()
        tab.show()
        self._app.processEvents()

        button_texts = [button.text() for button in tab.findChildren(QPushButton)]
        self.assertIn("Exportovat registr", button_texts)
        self.assertIn("Importovat registr", button_texts)

        registry_groups = [
            group for group in tab.findChildren(QGroupBox) if group.title() == "Registr právních požadavků"
        ]
        self.assertEqual(len(registry_groups), 1)
        card_layout = registry_groups[0].layout()
        assert card_layout is not None

        control_index = -1
        explanation_index = -1
        for index in range(card_layout.count()):
            item = card_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            if widget.objectName() == "registryControlsSection":
                control_index = index
            if widget.objectName() == "registryExplanationSection":
                explanation_index = index

        self.assertGreater(control_index, -1)
        self.assertGreater(explanation_index, -1)
        self.assertLess(control_index, explanation_index)

    def test_includes_and_excludes_are_two_columns(self) -> None:
        tab = LegalRegistryTransferTab()
        tab.show()
        self._app.processEvents()
        all_text = _collect_visible_text(tab)
        self.assertIn("Obsahuje", all_text)
        self.assertIn("Neobsahuje", all_text)
        self.assertIn("✔ Právní předpisy", all_text)
        self.assertIn("✖ Auditní metodiky", all_text)


class CodebookGroupTransferTestCase(unittest.TestCase):
    def test_group_export_creates_zip_with_manifest(self) -> None:
        target = storage_module.storage_service.exports_dir / "group-proverky.zip"
        result = codebook_export_service.export_group_codebooks(MODULE_PROVERKY, target)
        self.assertTrue(target.is_file())
        self.assertGreater(result.item_count, 0)

        with zipfile.ZipFile(target, "r") as zf:
            self.assertIn(MANIFEST_FILENAME, zf.namelist())
            manifest = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
            self.assertEqual(manifest.get("group_module"), MODULE_PROVERKY)

    def test_group_import_creates_safety_backup(self) -> None:
        target = storage_module.storage_service.exports_dir / "group-import.zip"
        codebook_export_service.export_group_codebooks(MODULE_PROVERKY, target)
        result = codebook_transfer_service.import_group_with_verified_safety(MODULE_PROVERKY, target)
        self.assertTrue(Path(result["safety_backup_path"]).is_file())
        self.assertTrue(result["safety_backup_manifest"].get("verified"))

    def test_group_import_skips_non_importable_entries(self) -> None:
        from moduly.sprava_dat.sluzby.codebook_import_service import codebook_import_service

        entries = codebook_catalog_service.list_group_entries("Modul Kniha úrazů")
        self.assertTrue(any(not entry.importable for entry in entries))
        summary = codebook_import_service.import_group_codebooks(
            "Modul Kniha úrazů",
            storage_module.storage_service.exports_dir / "missing.zip",
        )
        self.assertTrue(summary.errors)


class TeamCatalogCleanupTestCase(unittest.TestCase):
    def test_catalog_excludes_team_module_remnants(self) -> None:
        entries = codebook_catalog_service.list_codebooks()
        names = {entry.name.lower() for entry in entries}
        paths = {entry.path.lower() for entry in entries}
        self.assertFalse(any("role_v_tymu" in value for value in names | paths))
        self.assertFalse(any("typy_tymu" in value for value in names | paths))


class CodebooksGroupUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_group_selection_enables_export_group_button(self) -> None:
        tab = CodebooksTab()
        tab._show_group_details(MODULE_PROVERKY)
        self.assertTrue(tab.export_group_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
