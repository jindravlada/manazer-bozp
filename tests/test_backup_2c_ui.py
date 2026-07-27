"""BACKUP-2c: UI pro zálohu a obnovu *.mbbackup."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-2c-ui-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QDialog

    from core.backup import (
        BACKUP_EXTENSION,
        INTEGRITY_INVALID,
        INTEGRITY_VALID,
        RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
        RESTORE_ERR_FAILED_BEFORE_SWAP,
        RESTORE_ERR_ROLLBACK_FAILED,
        build_recovery_marker_payload,
        recovery_marker_path,
        write_recovery_marker,
    )
    from core.backup.package_integrity import BackupIntegrityIssue, BackupIntegrityReport
    from core.database.database_initializer import initialize_database
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
        instance_backup_workflow_service,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.tab_constants import TAB_BACKUP

    initialize_database()


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_ws(root: Path, note: str = "data") -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES (?)", (note,))
        conn.commit()
    finally:
        conn.close()
    for name in ("prilohy", "ciselniky", "templates", "konfigurace", "control_results"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    (workspace / "prilohy" / "a.txt").write_text(note, encoding="utf-8")
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    settings = root / "settings.json"
    settings.write_text(json.dumps({"marker": note}), encoding="utf-8")
    return workspace, db_path, settings


class InstanceBackupUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with patch.object(Path, "home", return_value=_HOME):
            importlib.reload(storage_module)
            storage_module.storage_service.ensure_structure()
        # Workflow drží vlastní referenci na storage_service – sjednotit po reloadu.
        wf_mod.storage_service = storage_module.storage_service
        self.service = InstanceBackupWorkflowService()
        self.parent = BackupTab()
        # reset global service block state
        instance_backup_workflow_service._restore_blocked = False
        instance_backup_workflow_service._active_markers = []

    def test_tab_label_is_backup_and_restore(self) -> None:
        self.assertEqual(TAB_BACKUP, "Zálohování a obnova")
        self.assertTrue(hasattr(self.parent, "create_mbbackup_button"))
        self.assertTrue(hasattr(self.parent, "verify_mbbackup_button"))
        self.assertTrue(hasattr(self.parent, "restore_mbbackup_button"))

    def test_create_backup_from_ui(self) -> None:
        from moduly.sprava_dat.sluzby.data_management_settings_service import (
            data_management_settings_service,
        )

        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

        target = _TMP / f"ui-create{BACKUP_EXTENSION}"
        target.write_bytes(b"mbbackup")
        with patch.object(
            wf_mod.QFileDialog, "getSaveFileName", return_value=(str(target), "")
        ):
            with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                with patch.object(wf_mod, "create_instance_backup") as mock_create:
                    meta = MagicMock()
                    meta.created_at = "2026-01-01T00:00:00+00:00"
                    meta.app_version = "3.1.1"
                    meta.files = []
                    meta.format_version = 1
                    meta.package_kind = "instance_backup"
                    meta.total_content_size = 0
                    meta.platform = "test"
                    mock_create.return_value = MagicMock(
                        path=target,
                        metadata=meta,
                        verified=True,
                        database_integrity="ok",
                    )
                    ok = self.service.create_instance_backup_ui(self.parent)
        self.assertTrue(ok)
        mock_create.assert_called_once()
        record = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertTrue(record.path.endswith(BACKUP_EXTENSION))
        self.assertTrue(record.manifest.get("verified"))

    def test_cancel_save_dialog(self) -> None:
        with patch.object(wf_mod.QFileDialog, "getSaveFileName", return_value=("", "")):
            ok = self.service.create_instance_backup_ui(self.parent)
        self.assertFalse(ok)

    def test_successful_verify(self) -> None:
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[])
        report.metadata = MagicMock(created_at="t", app_version="3.1.1")
        report.files_checked = 3
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/x.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                    ok = self.service.verify_instance_backup_ui(self.parent)
        self.assertTrue(ok)

    def test_invalid_backup_verify_display(self) -> None:
        report = BackupIntegrityReport(
            status=INTEGRITY_INVALID,
            issues=[
                BackupIntegrityIssue(code="bad_zip", message="Poškozený ZIP", severity="error")
            ],
        )
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/bad.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1) as dlg:
                    ok = self.service.verify_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        dlg.assert_called()

    def test_restore_blocked_for_invalid_backup(self) -> None:
        report = BackupIntegrityReport(
            status=INTEGRITY_INVALID,
            issues=[BackupIntegrityIssue(code="x", message="neplatná", severity="error")],
        )
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/bad.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                    with patch.object(wf_mod, "restore_instance_backup") as mock_restore:
                        ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        mock_restore.assert_not_called()

    def test_restore_confirm_accepted(self) -> None:
        meta = MagicMock(created_at="2026-07-01T12:00:00+00:00", app_version="3.1.1")
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)
        result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(wf_mod.RestoreConfirmDialog, "exec", return_value=QDialog.DialogCode.Accepted):
                    with patch.object(wf_mod, "dispose_database_engine", create=True):
                        with patch(
                            "core.database.session.dispose_database_engine"
                        ):
                            with patch.object(
                                wf_mod, "restore_instance_backup", return_value=result
                            ):
                                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                                    with patch.object(wf_mod.QMessageBox, "information"):
                                        with patch.object(QApplication, "quit") as quit_mock:
                                            ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertTrue(ok)
        quit_mock.assert_called_once()

    def test_restore_confirm_rejected(self) -> None:
        meta = MagicMock(created_at="t", app_version="3.1.1")
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(
                    wf_mod.RestoreConfirmDialog, "exec", return_value=QDialog.DialogCode.Rejected
                ):
                    with patch.object(wf_mod, "restore_instance_backup") as mock_restore:
                        ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        mock_restore.assert_not_called()

    def test_error_before_swap_message(self) -> None:
        meta = MagicMock(created_at="t", app_version="3.1.1")
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)
        err = wf_mod.InstanceRestoreError(
            RESTORE_ERR_FAILED_BEFORE_SWAP,
            "selhání",
            cause_code="write_error",
        )
        shown = {}

        def capture_init(self_dlg, parent, **kwargs):
            shown["kwargs"] = kwargs
            QDialog.__init__(self_dlg, parent)

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(
                    wf_mod.RestoreConfirmDialog, "exec", return_value=QDialog.DialogCode.Accepted
                ):
                    with patch("core.database.session.dispose_database_engine"):
                        with patch.object(wf_mod, "restore_instance_backup", side_effect=err):
                            with patch.object(
                                wf_mod.MessageWithDetailsDialog, "__init__", capture_init
                            ):
                                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                                    ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        self.assertIn("nebyla změněna", shown["kwargs"]["message"])

    def test_successful_rollback_message(self) -> None:
        meta = MagicMock(created_at="t", app_version="3.1.1")
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)
        err = wf_mod.InstanceRestoreError(
            RESTORE_ERR_FAILED_AFTER_SWAP_ROLLED_BACK,
            "rollback ok",
            rolled_back=True,
            cause_code="post_restore_check_failed",
        )
        shown = {}

        def capture_init(self_dlg, parent, **kwargs):
            shown["kwargs"] = kwargs
            QDialog.__init__(self_dlg, parent)

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(
                    wf_mod.RestoreConfirmDialog, "exec", return_value=QDialog.DialogCode.Accepted
                ):
                    with patch("core.database.session.dispose_database_engine"):
                        with patch.object(wf_mod, "restore_instance_backup", side_effect=err):
                            with patch.object(
                                wf_mod.MessageWithDetailsDialog, "__init__", capture_init
                            ):
                                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                                    self.service.restore_instance_backup_ui(self.parent)
        self.assertIn("vrácena", shown.get("kwargs", {}).get("message", "").lower())

    def test_rollback_failed_shows_marker(self) -> None:
        meta = MagicMock(created_at="t", app_version="3.1.1")
        report = BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)
        err = wf_mod.InstanceRestoreError(
            RESTORE_ERR_ROLLBACK_FAILED,
            "kritické",
            marker_path="/tmp/.mbrestore-in-progress-abc.json",
            preserved_paths=["/tmp/a", "/tmp/b"],
        )
        shown = {}

        def capture_init(self_dlg, parent, **kwargs):
            shown["kwargs"] = kwargs
            QDialog.__init__(self_dlg, parent)

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=report):
                with patch.object(wf_mod.RestoreConfirmDialog, "exec", return_value=QDialog.DialogCode.Accepted):
                    with patch("core.database.session.dispose_database_engine"):
                        with patch.object(wf_mod, "restore_instance_backup", side_effect=err):
                            with patch.object(
                                wf_mod.MessageWithDetailsDialog, "__init__", capture_init
                            ):
                                with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                                    self.service.restore_instance_backup_ui(self.parent)
        msg = shown.get("kwargs", {}).get("message", "")
        self.assertIn("mbrestore-in-progress", msg)

    def test_startup_marker_warning_and_block(self) -> None:
        parent_dir = storage_module.storage_service.base.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        marker = recovery_marker_path(parent_dir, "uitest")
        write_recovery_marker(
            marker,
            build_recovery_marker_payload(
                phase="rolling_back",
                started_at="2026-01-01T00:00:00+00:00",
                backup_format_version=1,
                package_path="/x.mbbackup",
                workspace_root=storage_module.storage_service.base,
                new_workspace=None,
                rollback_workspace=None,
                token="uitest",
            ),
        )
        try:
            with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                blocked = self.service.check_recovery_markers_at_startup(self.parent)
            self.assertTrue(blocked)
            self.assertTrue(self.service.restore_blocked)

            with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                with patch.object(wf_mod.QFileDialog, "getOpenFileName") as open_dlg:
                    ok = self.service.restore_instance_backup_ui(self.parent)
            self.assertFalse(ok)
            open_dlg.assert_not_called()
        finally:
            marker.unlink(missing_ok=True)

    def test_tab_disables_restore_when_marker_present(self) -> None:
        parent_dir = storage_module.storage_service.base.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        marker = recovery_marker_path(parent_dir, "tabblock")
        write_recovery_marker(
            marker,
            build_recovery_marker_payload(
                phase="after_swap",
                started_at="2026-01-01T00:00:00+00:00",
                backup_format_version=1,
                package_path="/x.mbbackup",
                workspace_root=storage_module.storage_service.base,
                new_workspace=None,
                rollback_workspace=None,
                token="tabblock",
            ),
        )
        try:
            instance_backup_workflow_service.refresh_recovery_markers()
            self.parent.refresh()
            self.assertFalse(self.parent.restore_mbbackup_button.isEnabled())
        finally:
            marker.unlink(missing_ok=True)
            instance_backup_workflow_service.refresh_recovery_markers()
            self.parent.refresh()


if __name__ == "__main__":
    unittest.main()
