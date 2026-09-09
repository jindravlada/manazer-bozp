"""BACKUP-UX-1: poslední kompletní záloha je *.mbbackup (Souhrn / Stav dat)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-ux-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.backup.constants import BACKUP_EXTENSION
    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.sprava_dat.sluzby import instance_backup_create_operation as create_op_mod
    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BACKUP_TYPE_INSTANCE,
        BackupRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.sluzby.data_management_status_service import (
        data_management_status_service,
    )
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage


class BackupUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        data_management_settings_service.save_last_diagnostic(
            {"created_at": "2026-07-10T10:00:00", "summary": "ok"}
        )

    def test_create_updates_summary_and_status(self) -> None:
        page = SpravaDatPage()
        target = storage_module.storage_service.backups_dir / f"ux1{BACKUP_EXTENSION}"
        target.write_bytes(b"mbbackup")

        service = InstanceBackupWorkflowService()
        meta = MagicMock()
        meta.created_at = "2026-07-20T08:00:00"
        meta.app_version = "3.1.1"
        meta.files = [1, 2]
        meta.format_version = 1
        meta.package_kind = "instance_backup"
        meta.total_content_size = 10
        meta.platform = "test"

        with patch.object(
            wf_mod.QFileDialog, "getSaveFileName", return_value=(str(target), "")
        ):
            with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                with patch.object(
                    create_op_mod,
                    "create_instance_backup",
                    return_value=MagicMock(
                        path=target,
                        metadata=meta,
                        verified=True,
                        database_integrity="ok",
                    ),
                ):
                    ok = service.create_instance_backup_ui(page.backup_tab)

        self.assertTrue(ok)
        page.refresh_backup_status()

        record = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.backup_type, BACKUP_TYPE_INSTANCE)
        self.assertTrue(record.path.endswith(BACKUP_EXTENSION))

        self.assertIn(target.name, page.summary_tab.backup_summary_label.text())
        self.assertIn("ověřena", page.summary_tab.backup_summary_label.text())
        self.assertNotIn("nebyl nalezen", page.summary_tab.warnings_label.text())
        self.assertNotIn(
            "dosud nebyla vytvořena", page.summary_tab.warnings_label.text()
        )

        status, warnings = data_management_status_service.compute_status()
        self.assertEqual(status, "V pořádku")
        self.assertFalse(any("záloha" in w.lower() for w in warnings))

    def test_stale_zip_cleared_on_refresh(self) -> None:
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-01-01T00:00:00",
                path=str(storage_module.storage_service.backups_dir / "old.zip"),
                manifest={"verified": True},
                backup_type="celkova",
            )
        )
        page = SpravaDatPage()
        page.refresh_backup_status()
        self.assertIsNone(data_management_settings_service.get_last_backup())
        self.assertIn("nikdy nevytvořena", page.summary_tab.backup_summary_label.text())


if __name__ == "__main__":
    unittest.main()
