import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QTabWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.file_location_service import open_path_in_file_manager
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BackupRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import TAB_SUMMARY


class DataManagementSettingsServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_last_backup_persists_and_reloads(self) -> None:
        record = BackupRecord(
            created_at="2026-07-10T10:15:30",
            path=str(storage_module.storage_service.backups_dir / "demo.mbbackup"),
            manifest={"verified": True, "file_count": 3},
            backup_type="instance_backup",
        )
        data_management_settings_service.save_last_backup(record)

        loaded = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.path, record.path)
        self.assertEqual(loaded.manifest["file_count"], 3)
        self.assertEqual(loaded.backup_type, "instance_backup")

    def test_zip_last_backup_is_ignored(self) -> None:
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T10:15:30",
                path=str(storage_module.storage_service.backups_dir / "legacy.zip"),
                manifest={"verified": True},
                backup_type="celkova",
            )
        )
        self.assertIsNone(data_management_settings_service.get_last_backup())
        self.assertTrue(data_management_settings_service.clear_stale_zip_last_backup())
        self.assertIsNone(data_management_settings_service.get_last_backup())


class BackupTabTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self.tab = BackupTab()

    def test_mbbackup_controls_visible_without_legacy_zip_ui(self) -> None:
        self.assertTrue(hasattr(self.tab, "create_mbbackup_button"))
        self.assertTrue(hasattr(self.tab, "verify_mbbackup_button"))
        self.assertTrue(hasattr(self.tab, "restore_mbbackup_button"))
        self.assertTrue(hasattr(self.tab, "recovery_diag_button"))
        self.assertFalse(hasattr(self.tab, "create_backup_button"))
        self.assertFalse(hasattr(self.tab, "restore_backup_button"))
        self.assertFalse(hasattr(self.tab, "last_backup_label"))
        text = "\n".join(label.text() for label in self.tab.findChildren(QLabel))
        titles = "\n".join(group.title() for group in self.tab.findChildren(QGroupBox))
        combined = f"{text}\n{titles}"
        self.assertIn("*.mbbackup", combined)
        self.assertNotIn("Dřívější formát", combined)
        self.assertNotIn("kompletní ZIP", combined.lower())
        self.assertNotIn("Vytvořit kompletní zálohu", combined)


class SpravaDatPageBackupTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_page_opens_on_summary_tab(self) -> None:
        page = SpravaDatPage()
        tabs = page.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        assert tabs is not None
        self.assertEqual(tabs.tabText(tabs.currentIndex()), TAB_SUMMARY)

        page.refresh()
        self.assertEqual(tabs.currentIndex(), 0)
        self.assertEqual(tabs.tabText(0), TAB_SUMMARY)


class FileLocationServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_open_path_in_file_manager_warns_when_missing(self) -> None:
        missing = storage_module.storage_service.backups_dir / "missing-dir" / "missing.zip"
        with patch("core.services.file_location_service.QMessageBox.warning") as mock_warning:
            with patch("core.services.file_location_service.QMessageBox.question") as mock_question:
                opened = open_path_in_file_manager(missing)
        self.assertFalse(opened)
        mock_warning.assert_called_once()
        mock_question.assert_not_called()


if __name__ == "__main__":
    unittest.main()
