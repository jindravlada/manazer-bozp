import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.backup_manifest_service import backup_manifest_service
    from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
    from core.services.file_location_service import open_path_in_file_manager
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BackupRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import TAB_BACKUP, TAB_SUMMARY


class BackupManifestServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def test_manifest_matches_created_backup_zip(self) -> None:
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)

        with zipfile.ZipFile(backup_path, "r") as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
            catalog_paths = backup_manifest_service._zip_catalog_paths(names)
            expected = backup_manifest_service._count_paths(catalog_paths)

        self.assertTrue(manifest["verified"])
        self.assertEqual(manifest["file_count"], len(names))
        self.assertEqual(manifest["global_catalogs"], expected["global_catalogs"])
        self.assertEqual(manifest["module_catalogs"], expected["module_catalogs"])
        self.assertEqual(manifest["audit_methodologies"], expected["audit_methodologies"])
        self.assertEqual(manifest["proverky_methodologies"], expected["proverky_methodologies"])
        self.assertIn("database_counts", manifest)

    def test_unreadable_zip_is_not_verified(self) -> None:
        broken = storage_module.storage_service.backups_dir / "broken.zip"
        broken.write_text("not-a-zip", encoding="utf-8")

        manifest = backup_manifest_service.build_manifest(broken)

        self.assertFalse(manifest["verified"])
        self.assertFalse(manifest["zip_readable"])


class DataManagementSettingsServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

    def test_last_backup_persists_and_reloads(self) -> None:
        record = BackupRecord(
            created_at="2026-07-10T10:15:30",
            path=str(storage_module.storage_service.backups_dir / "demo.zip"),
            manifest={"verified": True, "file_count": 3},
            backup_type=BACKUP_TYPE_FULL,
        )
        data_management_settings_service.save_last_backup(record)

        loaded = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.path, record.path)
        self.assertEqual(loaded.manifest["file_count"], 3)
        self.assertEqual(loaded.backup_type, BACKUP_TYPE_FULL)


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

    def test_create_backup_uses_existing_service_and_persists_last_backup(self) -> None:
        target = storage_module.storage_service.backups_dir / "sprava-dat-test.zip"

        with patch(
            "moduly.sprava_dat.ui.backup_tab.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch("moduly.sprava_dat.ui.backup_tab.QMessageBox.information"):
                self.tab._create_full_backup()

        record = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(Path(record.path).is_file())
        self.assertTrue(record.manifest.get("verified"))

        self.tab.refresh()
        self.assertIn(Path(record.path).name, self.tab.last_backup_label.text())

    def test_failed_verification_does_not_save_last_backup(self) -> None:
        target = storage_module.storage_service.backups_dir / "invalid-backup.zip"

        with patch(
            "moduly.sprava_dat.ui.backup_tab.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.backup_tab.backup_service.create_backup",
                return_value=target,
            ):
                with patch(
                    "moduly.sprava_dat.ui.backup_tab.backup_service.verify_backup_integrity",
                    return_value={"verified": False, "verification_errors": ["test"]},
                ):
                    with patch("moduly.sprava_dat.ui.backup_tab.QMessageBox.critical"):
                        self.tab._create_full_backup()

        self.assertIsNone(data_management_settings_service.get_last_backup())

    def test_open_location_uses_backup_path(self) -> None:
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T12:00:00",
                path=str(backup_path),
                manifest={"verified": True},
                backup_type=BACKUP_TYPE_FULL,
            )
        )

        with patch(
            "moduly.sprava_dat.ui.backup_tab.open_path_in_file_manager",
            return_value=True,
        ) as mock_open:
            self.tab._open_last_backup_location()

        mock_open.assert_called_once_with(str(backup_path.resolve()), parent=self.tab, title="Umístění zálohy")

    def test_restore_creates_verified_safety_backup(self) -> None:
        source = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)

        with patch(
            "moduly.sprava_dat.ui.backup_tab.QFileDialog.getOpenFileName",
            return_value=(str(source), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.backup_tab.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                with patch("moduly.sprava_dat.ui.backup_tab.QMessageBox.information"):
                    with patch("PySide6.QtWidgets.QApplication.quit"):
                        self.tab._restore_full_backup()

        safety = data_management_settings_service.get_last_pre_restore_backup()
        self.assertIsNotNone(safety)
        assert safety is not None
        self.assertTrue(Path(safety.path).is_file())
        self.assertTrue(safety.manifest.get("verified"))

        restore_result = data_management_settings_service.get_last_restore_result()
        self.assertIsNotNone(restore_result)
        assert restore_result is not None
        self.assertEqual(restore_result.get("restored_path"), str(source.resolve()))
        self.assertEqual(restore_result.get("safety_backup_path"), safety.path)

    def test_failed_safety_backup_blocks_restore(self) -> None:
        source = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)

        with patch(
            "moduly.sprava_dat.ui.backup_tab.QFileDialog.getOpenFileName",
            return_value=(str(source), ""),
        ):
            with patch(
                "moduly.sprava_dat.ui.backup_tab.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                with patch(
                    "moduly.sprava_dat.ui.backup_tab.backup_service.restore_backup_with_verified_safety",
                    side_effect=ValueError("Bezpečnostní záloha se nepodařila ověřit."),
                ):
                    with patch("moduly.sprava_dat.ui.backup_tab.QMessageBox.critical") as mock_critical:
                        self.tab._restore_full_backup()

        mock_critical.assert_called_once()
        self.assertIsNone(data_management_settings_service.get_last_pre_restore_backup())


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
        missing = storage_module.storage_service.backups_dir / "missing.zip"
        with patch("core.services.file_location_service.QMessageBox.warning") as mock_warning:
            opened = open_path_in_file_manager(missing)
        self.assertFalse(opened)
        mock_warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
