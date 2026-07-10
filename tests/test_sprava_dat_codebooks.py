import importlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QSplitter, QTreeWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
    from moduly.sprava_dat.sluzby.codebook_catalog_service import (
        MODULE_AUDITY,
        MODULE_GLOBAL,
        MODULE_KNIHA_URAZU,
        MODULE_PROVERKY,
        MODULE_RIDICI,
        MODULE_VYSETROVANI_MU,
        codebook_catalog_service,
    )
    from moduly.sprava_dat.sluzby.codebook_export_service import codebook_export_service
    from moduly.sprava_dat.sluzby.codebook_import_service import codebook_import_service
    from moduly.sprava_dat.sluzby.codebook_manifest_service import (
        MANIFEST_FILENAME,
        codebook_manifest_service,
    )
    from moduly.sprava_dat.sluzby.codebook_transfer_service import codebook_transfer_service
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        CodebooksExportRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.ui.codebooks_tab import CodebooksTab
    from moduly.sprava_dat.ui.summary_tab import SummaryTab
    from moduly.sprava_dat.ui.tab_constants import TAB_CODEBOOKS


class CodebookCatalogServiceTestCase(unittest.TestCase):
    def test_lists_all_codebooks_once(self) -> None:
        entries = codebook_catalog_service.list_codebooks()
        ids = [entry.codebook_id for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(entries), 20)

    def test_grouped_by_modules(self) -> None:
        grouped = codebook_catalog_service.grouped_codebooks()
        modules = set(grouped.keys())
        self.assertIn(MODULE_GLOBAL, modules)
        self.assertIn(MODULE_KNIHA_URAZU, modules)
        self.assertIn(MODULE_PROVERKY, modules)
        self.assertIn(MODULE_AUDITY, modules)
        self.assertIn(MODULE_RIDICI, modules)
        self.assertIn(MODULE_VYSETROVANI_MU, modules)

        global_names = {entry.name for entry in grouped[MODULE_GLOBAL]}
        self.assertIn("Pracoviště", global_names)
        self.assertIn("THP pracovníci", global_names)

        kniha_names = {entry.name for entry in grouped[MODULE_KNIHA_URAZU]}
        self.assertIn("Druhy zranění", kniha_names)
        self.assertIn("Zdravotní pojišťovny", kniha_names)

    def test_selected_entry_details(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.module, MODULE_GLOBAL)
        self.assertEqual(entry.storage_type, "databáze")
        self.assertTrue(entry.exportable)
        self.assertTrue(entry.importable)


class CodebookExportImportServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_single_json_export_and_import(self) -> None:
        entry = codebook_catalog_service.get_by_id("json:proverky/oblasti.json")
        self.assertIsNotNone(entry)
        assert entry is not None

        target = storage_module.storage_service.exports_dir / "oblasti-export.json"
        result = codebook_export_service.export_codebook(entry, target)
        self.assertTrue(target.is_file())
        self.assertGreater(result.item_count, 0)
        self.assertTrue(result.manifest.get("verified"))

        modified = json.loads(target.read_text(encoding="utf-8"))
        areas = modified.get("oblasti") or []
        if areas and isinstance(areas[0], dict):
            areas[0]["test_marker"] = "86f"
            target.write_text(json.dumps(modified, ensure_ascii=False, indent=2), encoding="utf-8")

        summary = codebook_import_service.import_codebook(entry, target)
        self.assertIn(entry.name, summary.updated)

        reloaded = json.loads(Path(entry.path).read_text(encoding="utf-8"))
        self.assertEqual((reloaded.get("oblasti") or [{}])[0].get("test_marker"), "86f")

    def test_bulk_export_contains_manifest_and_codebooks(self) -> None:
        target = storage_module.storage_service.exports_dir / "ciselniky-all.zip"
        result = codebook_export_service.export_all_codebooks(target)
        self.assertTrue(target.is_file())
        self.assertGreater(result.item_count, 10)

        with zipfile.ZipFile(target, "r") as zf:
            self.assertIn(MANIFEST_FILENAME, zf.namelist())
            manifest = json.loads(zf.read(MANIFEST_FILENAME).decode("utf-8"))
            self.assertGreater(len(manifest.get("codebooks") or []), 10)
            self.assertTrue(any(name.startswith("ciselniky/") for name in zf.namelist()))

        verified = codebook_manifest_service.verify_bulk_export(target)
        self.assertTrue(verified.get("verified"))

    def test_bulk_import_creates_safety_backup(self) -> None:
        target = storage_module.storage_service.exports_dir / "ciselniky-import.zip"
        codebook_export_service.export_all_codebooks(target)

        result = codebook_transfer_service.import_with_verified_safety(target)

        self.assertTrue(Path(result["safety_backup_path"]).is_file())
        self.assertTrue(result["safety_backup_manifest"].get("verified"))
        self.assertIn("import_result", result)

    def test_single_export_manifest_fields(self) -> None:
        entry = codebook_catalog_service.get_by_id("json:audity/procesy.json")
        self.assertIsNotNone(entry)
        assert entry is not None
        target = storage_module.storage_service.exports_dir / "procesy-export.json"
        result = codebook_export_service.export_codebook(entry, target)
        rows = codebook_manifest_service.rows_from_single_manifest(result.manifest)
        labels = [row[0] for row in rows]
        self.assertIn("Soubor", labels)
        self.assertIn("Počet položek", labels)
        self.assertIn("Velikost souboru", labels)


class CodebooksTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = CodebooksTab()

    def test_tab_has_splitter_and_catalog_tree(self) -> None:
        self.assertIsNotNone(self.tab.findChild(QTreeWidget))
        splitters = self.tab.findChildren(QSplitter)
        self.assertGreaterEqual(len(splitters), 2)

    def test_catalog_tree_contains_module_groups(self) -> None:
        self.tab.refresh()
        top_level_texts = [
            self.tab.catalog_tree.topLevelItem(index).text(0)
            for index in range(self.tab.catalog_tree.topLevelItemCount())
        ]
        self.assertIn("Globální číselníky", top_level_texts)
        self.assertIn("Modul Kniha úrazů", top_level_texts)
        self.assertIn("Prověrky", top_level_texts)

    def test_bulk_export_persists_settings(self) -> None:
        target = storage_module.storage_service.exports_dir / "ui-bulk-export.zip"

        with patch(
            "moduly.sprava_dat.ui.codebooks_tab.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch.object(QMessageBox, "information"):
                self.tab._export_all()

        record = data_management_settings_service.get_last_codebooks_export()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(Path(record.path).is_file())
        self.assertEqual(record.export_type, "bulk")

    def test_selected_codebook_shows_details(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:thp_workers")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.tab._show_entry_details(entry)
        self.assertIn("THP pracovníci", self.tab.detail_name.text())
        self.assertIn(MODULE_GLOBAL, self.tab.detail_module.text())


class SummaryTabCodebooksTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = SummaryTab(navigate_callback=lambda _key: None)

    def test_summary_shows_codebooks_section(self) -> None:
        self.tab.refresh()
        self.assertIn("Počet evidovaných číselníků", self.tab.codebooks_summary_label.text())
        self.assertGreater(codebook_catalog_service.count_all(), 0)

    def test_summary_shows_last_export_and_import(self) -> None:
        export_path = storage_module.storage_service.exports_dir / "summary-export.zip"
        codebook_export_service.export_all_codebooks(export_path)
        data_management_settings_service.save_last_codebooks_export(
            CodebooksExportRecord(
                created_at="2026-07-10T12:00:00",
                path=str(export_path),
                manifest=codebook_manifest_service.verify_bulk_export(export_path),
                export_type="bulk",
            )
        )
        self.tab.refresh()
        self.assertIn("Poslední export:", self.tab.codebooks_summary_label.text())
        self.assertIn("10.07.2026 12:00:00", self.tab.codebooks_summary_label.text())


if __name__ == "__main__":
    unittest.main()
