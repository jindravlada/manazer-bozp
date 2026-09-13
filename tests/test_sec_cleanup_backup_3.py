"""SEC-CLEANUP-BACKUP-3: obnova bez ověřené safety zálohy se nespustí."""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog

from core.backup import INTEGRITY_VALID, InstanceBackupError
from core.backup.package_integrity import BackupIntegrityReport

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-cleanup-backup-3"
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

    from moduly.sprava_dat.sluzby import instance_backup_restore_operation as restore_op_mod
    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui import instance_backup_dialogs as dialogs_mod
    from moduly.sprava_dat.ui.backup_tab import BackupTab


def _valid_report() -> BackupIntegrityReport:
    meta = MagicMock(created_at="2026-07-01T12:00:00+00:00", app_version="3.2.0")
    return BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)


class SecCleanupBackup3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with patch.object(Path, "home", return_value=_HOME):
            importlib.reload(storage_module)
            storage_module.storage_service.ensure_structure()
        wf_mod.storage_service = storage_module.storage_service
        self.service = InstanceBackupWorkflowService()
        self.parent = BackupTab()
        self.canary = storage_module.storage_service.base / "SEC-BACKUP-3-CANARY.txt"
        self.canary.write_text("workspace-before-restore", encoding="utf-8")

    def _run_restore(
        self,
        *,
        create_side_effect,
        restore_side_effect=None,
    ) -> tuple[bool, MagicMock, list[dict]]:
        dialog_calls: list[dict] = []

        def fake_dialog(*_args, **kwargs):
            dialog_calls.append(kwargs)
            mock = MagicMock()
            mock.exec.return_value = 1
            return mock

        restore_mock = MagicMock(side_effect=restore_side_effect)
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
                        side_effect=create_side_effect,
                    ):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                restore_op_mod,
                                "restore_instance_backup",
                                restore_mock,
                            ):
                                with patch.object(
                                    wf_mod, "MessageWithDetailsDialog", side_effect=fake_dialog
                                ):
                                    with patch.object(wf_mod.QMessageBox, "information"):
                                        with patch.object(QApplication, "quit"):
                                            ok = self.service.restore_instance_backup_ui(
                                                self.parent
                                            )
        return ok, restore_mock, dialog_calls

    def test_a_successful_safety_backup_allows_restore(self) -> None:
        safety_file = storage_module.storage_service.backups_dir / "AUTO.mbbackup"
        safety_file.write_bytes(b"safety")
        create_result = MagicMock()
        create_result.path = str(safety_file)
        restore_result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )

        ok, restore_mock, _calls = self._run_restore(
            create_side_effect=lambda *_a, **_k: create_result,
            restore_side_effect=lambda *_a, **_k: restore_result,
        )
        self.assertTrue(ok)
        restore_mock.assert_called_once()

    def test_b_safety_create_failure_does_not_start_restore(self) -> None:
        ok, restore_mock, calls = self._run_restore(
            create_side_effect=InstanceBackupError("disk full"),
        )
        self.assertFalse(ok)
        restore_mock.assert_not_called()
        self.assertTrue(calls)
        self.assertEqual(calls[0]["title"], "Obnova ze zálohy")
        self.assertEqual(calls[0]["message"], wf_mod._SAFETY_BACKUP_FAILED_USER_MESSAGE)
        self.assertIn("disk full", calls[0]["details"])
        self.assertEqual(self.canary.read_text(encoding="utf-8"), "workspace-before-restore")

    def test_c_safety_verify_failure_does_not_start_restore(self) -> None:
        ok, restore_mock, calls = self._run_restore(
            create_side_effect=InstanceBackupError(
                "Bezpečnostní záloha se nepodařila ověřit."
            ),
        )
        self.assertFalse(ok)
        restore_mock.assert_not_called()
        self.assertTrue(calls)
        self.assertEqual(calls[0]["message"], wf_mod._SAFETY_BACKUP_FAILED_USER_MESSAGE)
        self.assertIn("nepodařila ověřit", calls[0]["details"])
        self.assertEqual(self.canary.read_text(encoding="utf-8"), "workspace-before-restore")

    def test_d_workspace_unchanged_when_safety_backup_fails(self) -> None:
        before = self.canary.read_text(encoding="utf-8")
        db_path = storage_module.storage_service.database_path
        db_mtime = db_path.stat().st_mtime if db_path.exists() else None
        self.test_b_safety_create_failure_does_not_start_restore()
        self.test_c_safety_verify_failure_does_not_start_restore()
        self.assertEqual(self.canary.read_text(encoding="utf-8"), before)
        if db_mtime is not None:
            self.assertEqual(db_path.stat().st_mtime, db_mtime)

    def test_e_continue_without_safety_dialog_removed(self) -> None:
        self.assertFalse(hasattr(dialogs_mod, "ContinueWithoutSafetyBackupDialog"))
        source = inspect.getsource(InstanceBackupWorkflowService.restore_instance_backup_ui)
        self.assertNotIn("ContinueWithoutSafetyBackupDialog", source)
        self.assertNotIn("Pokračovat bez bezpečnostní zálohy", source)
        self.assertNotIn("vědomě pokračoval", source)
        self.assertIn("_SAFETY_BACKUP_FAILED_USER_MESSAGE", source)


if __name__ == "__main__":
    unittest.main()
