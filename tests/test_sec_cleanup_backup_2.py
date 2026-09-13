"""SEC-CLEANUP-BACKUP-2: current backup workflow už application ZIP nenabízí."""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from core.backup.constants import BACKUP_EXTENSION
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-cleanup-backup-2"
_HOME = _TEST_ROOT / "home"

if _TEST_ROOT.exists():
    shutil.rmtree(_TEST_ROOT)
_HOME.mkdir(parents=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.backup import create_instance_backup, inspect_backup_integrity
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage


class SecCleanupBackup2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_legacy_zip_backup_modules_are_gone(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("core.services.backup_service")
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("core.services.backup_manifest_service")
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("moduly.sprava_dat.sluzby.full_backup_workflow_service")

    def test_backup_tab_does_not_offer_application_zip(self) -> None:
        tab = BackupTab()
        titles = [group.title() for group in tab.findChildren(QGroupBox)]
        self.assertEqual(titles, ["Úplná záloha Manažera BOZP (*.mbbackup)"])
        text = "\n".join(label.text() for label in tab.findChildren(QLabel))
        combined = text + "\n" + "\n".join(titles)
        self.assertIn("*.mbbackup", combined)
        self.assertNotIn("*.zip", combined)
        self.assertNotIn("ZIP záloha", combined)
        self.assertNotIn("Vytvořit kompletní zálohu", combined)
        self.assertNotIn("Obnovit kompletní zálohu", combined)
        self.assertFalse(hasattr(tab, "create_backup_button"))
        self.assertFalse(hasattr(tab, "restore_backup_button"))

    def test_instance_workflow_file_dialogs_use_mbbackup_only(self) -> None:
        source = inspect.getsource(InstanceBackupWorkflowService)
        self.assertIn(f"*{BACKUP_EXTENSION}", source)
        self.assertNotIn("*.zip", source)
        self.assertNotIn("ZIP záloha", source)

    def test_create_instance_backup_writes_mbbackup_not_zip(self) -> None:
        target = (
            storage_module.storage_service.backups_dir
            / f"sec-cleanup-backup-2{BACKUP_EXTENSION}"
        )
        result = create_instance_backup(target)
        self.assertEqual(result.path.suffix, BACKUP_EXTENSION)
        self.assertTrue(inspect_backup_integrity(result.path).ok)
        self.assertEqual(list(storage_module.storage_service.backups_dir.glob("*.zip")), [])

    def test_sprava_dat_page_uses_mbbackup_tab(self) -> None:
        page = SpravaDatPage()
        self.assertIsInstance(page.backup_tab, BackupTab)
        self.assertTrue(hasattr(page.backup_tab, "create_mbbackup_button"))
        self.assertFalse(hasattr(page.backup_tab, "create_backup_button"))


if __name__ == "__main__":
    unittest.main()
