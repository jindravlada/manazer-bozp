"""BACKUP-RESTORE-SAFE-2: selhání bezpečnostní zálohy obnovu nespustí."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-restore-safe-2-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QDialog

    from core.backup import INTEGRITY_VALID, InstanceBackupError
    from core.backup.package_integrity import BackupIntegrityReport
    from core.database.database_initializer import initialize_database
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from moduly.sprava_dat.sluzby import instance_backup_restore_operation as restore_op_mod
    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui import instance_backup_dialogs as dialogs_mod
    from moduly.sprava_dat.ui.backup_tab import BackupTab

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _valid_report() -> BackupIntegrityReport:
    meta = MagicMock(created_at="2026-07-01T12:00:00+00:00", app_version="3.2.0")
    return BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)


class BackupRestoreSafe2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with patch.object(Path, "home", return_value=_HOME):
            importlib.reload(storage_module)
            storage_module.storage_service.ensure_structure()
        wf_mod.storage_service = storage_module.storage_service
        self.service = InstanceBackupWorkflowService()
        self.parent = BackupTab()

    def test_continue_without_safety_dialog_is_gone(self) -> None:
        self.assertFalse(hasattr(dialogs_mod, "ContinueWithoutSafetyBackupDialog"))
        self.assertFalse(hasattr(wf_mod, "ContinueWithoutSafetyBackupDialog"))

    def test_error_dialog_not_shown_when_safety_succeeds(self) -> None:
        safety = MagicMock(path=str(storage_module.storage_service.backups_dir / "AUTO.mbbackup"))
        restore_result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )
        shown: list[dict] = []

        def fake_dialog(*_args, **kwargs):
            shown.append(kwargs)
            mock = MagicMock()
            mock.exec.return_value = 1
            return mock

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=QDialog.DialogCode.Accepted,
                ):
                    with patch.object(restore_op_mod, "create_instance_backup", return_value=safety):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                restore_op_mod, "restore_instance_backup", return_value=restore_result
                            ):
                                with patch.object(
                                    wf_mod, "MessageWithDetailsDialog", side_effect=fake_dialog
                                ):
                                    with patch.object(wf_mod.QMessageBox, "information"):
                                        with patch.object(QApplication, "quit"):
                                            ok = self.service.restore_instance_backup_ui(
                                                self.parent
                                            )
        self.assertTrue(ok)
        self.assertTrue(shown)
        self.assertNotEqual(
            shown[0].get("message"),
            wf_mod._SAFETY_BACKUP_FAILED_USER_MESSAGE,
        )

    def test_safety_failure_blocks_restore_and_shows_error(self) -> None:
        shown: list[dict] = []

        def fake_dialog(*_args, **kwargs):
            shown.append(kwargs)
            mock = MagicMock()
            mock.exec.return_value = 1
            return mock

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=QDialog.DialogCode.Accepted,
                ):
                    with patch.object(
                        restore_op_mod,
                        "create_instance_backup",
                        side_effect=InstanceBackupError("disk full"),
                    ):
                        with patch.object(
                            wf_mod, "MessageWithDetailsDialog", side_effect=fake_dialog
                        ):
                            with patch.object(restore_op_mod, "restore_instance_backup") as mock_restore:
                                ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        mock_restore.assert_not_called()
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0]["message"], wf_mod._SAFETY_BACKUP_FAILED_USER_MESSAGE)
        self.assertIn("disk full", shown[0]["details"])

    def test_workflow_has_no_continue_without_safety_path(self) -> None:
        source = inspect.getsource(InstanceBackupWorkflowService.restore_instance_backup_ui)
        self.assertNotIn("create_safety = False", source)
        self.assertNotIn("Pokračovat bez bezpečnostní zálohy", source)
        self.assertNotIn("vědomě pokračoval", source)


if __name__ == "__main__":
    unittest.main()
