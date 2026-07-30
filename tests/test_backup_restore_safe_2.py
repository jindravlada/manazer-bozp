"""BACKUP-RESTORE-SAFE-2: pokračování obnovy při selhání bezpečnostní zálohy."""

from __future__ import annotations

import importlib
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

    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.instance_backup_dialogs import (
        ContinueWithoutSafetyBackupDialog,
    )

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

    def test_dialog_continue_button_gated_by_checkbox(self) -> None:
        dialog = ContinueWithoutSafetyBackupDialog(self.parent)
        self.assertEqual(
            dialog.windowTitle(),
            "Nepodařilo se vytvořit bezpečnostní zálohu",
        )
        self.assertFalse(dialog.continue_button.isEnabled())
        self.assertTrue(dialog.cancel_button.isDefault())
        dialog.confirm_checkbox.setChecked(True)
        self.assertTrue(dialog.continue_button.isEnabled())
        dialog.confirm_checkbox.setChecked(False)
        self.assertFalse(dialog.continue_button.isEnabled())

    def test_crisis_dialog_not_shown_when_safety_succeeds(self) -> None:
        safety = MagicMock(path=str(storage_module.storage_service.backups_dir / "AUTO.mbbackup"))
        restore_result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=QDialog.DialogCode.Accepted,
                ):
                    with patch.object(wf_mod, "create_instance_backup", return_value=safety):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                wf_mod, "restore_instance_backup", return_value=restore_result
                            ):
                                with patch.object(
                                    wf_mod.ContinueWithoutSafetyBackupDialog, "exec"
                                ) as crisis_exec:
                                    with patch.object(
                                        wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                    ):
                                        with patch.object(wf_mod.QMessageBox, "information"):
                                            with patch.object(QApplication, "quit"):
                                                ok = self.service.restore_instance_backup_ui(
                                                    self.parent
                                                )
        self.assertTrue(ok)
        crisis_exec.assert_not_called()

    def test_crisis_dialog_shown_when_safety_fails(self) -> None:
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
                        wf_mod,
                        "create_instance_backup",
                        side_effect=InstanceBackupError("disk full"),
                    ):
                        with patch.object(
                            wf_mod.ContinueWithoutSafetyBackupDialog,
                            "exec",
                            return_value=QDialog.DialogCode.Rejected,
                        ) as crisis_exec:
                            with patch.object(wf_mod, "restore_instance_backup") as mock_restore:
                                ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        crisis_exec.assert_called_once()
        mock_restore.assert_not_called()

    def test_cancel_does_not_restore(self) -> None:
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
                        wf_mod,
                        "create_instance_backup",
                        side_effect=InstanceBackupError("selhání"),
                    ):
                        with patch.object(
                            wf_mod.ContinueWithoutSafetyBackupDialog,
                            "exec",
                            return_value=QDialog.DialogCode.Rejected,
                        ):
                            with patch.object(wf_mod, "restore_instance_backup") as mock_restore:
                                ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        mock_restore.assert_not_called()

    def test_continue_without_safety_runs_restore_and_logs(self) -> None:
        restore_result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )
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
                        wf_mod,
                        "create_instance_backup",
                        side_effect=InstanceBackupError("disk full"),
                    ):
                        with patch.object(
                            wf_mod.ContinueWithoutSafetyBackupDialog,
                            "exec",
                            return_value=QDialog.DialogCode.Accepted,
                        ):
                            with patch("core.database.session.dispose_database_engine"):
                                with patch.object(
                                    wf_mod,
                                    "restore_instance_backup",
                                    return_value=restore_result,
                                ) as mock_restore:
                                    with patch.object(
                                        wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                    ):
                                        with patch.object(wf_mod.QMessageBox, "information"):
                                            with patch.object(QApplication, "quit"):
                                                with self.assertLogs(
                                                    wf_mod.logger.name, level="WARNING"
                                                ) as logs:
                                                    ok = self.service.restore_instance_backup_ui(
                                                        self.parent
                                                    )
        self.assertTrue(ok)
        mock_restore.assert_called_once()
        joined = "\n".join(logs.output)
        self.assertIn("Automatická bezpečnostní záloha před obnovou selhala", joined)
        self.assertIn("vědomě pokračoval", joined)


if __name__ == "__main__":
    unittest.main()
