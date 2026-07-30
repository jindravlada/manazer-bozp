"""BACKUP-RESTORE-SAFE-1: automatická nouzová záloha před obnovou."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-restore-safe-1-"))
_HOME = _TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_HOME):
    from PySide6.QtWidgets import QApplication, QDialog

    from core.backup import (
        BACKUP_EXTENSION,
        INTEGRITY_VALID,
        RESTORE_ERR_FAILED_BEFORE_SWAP,
        InstanceBackupError,
        InstanceRestoreError,
        auto_before_restore_backup_filename,
        create_instance_backup,
    )
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
    for name in ("prilohy", "ciselniky", "templates", "konfigurace", "zalohy"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    (workspace / "prilohy" / "a.txt").write_text(note, encoding="utf-8")
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    settings = root / "settings.json"
    settings.write_text(json.dumps({"marker": note}), encoding="utf-8")
    return workspace, db_path, settings


def _valid_report() -> BackupIntegrityReport:
    meta = MagicMock(created_at="2026-07-01T12:00:00+00:00", app_version="3.2.0")
    return BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)


class BackupRestoreSafe1TestCase(unittest.TestCase):
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

    def test_auto_before_restore_filename_format(self) -> None:
        name = auto_before_restore_backup_filename("2026-07-30_22-15-01")
        self.assertEqual(name, f"AUTO_BEFORE_RESTORE_2026-07-30_22-15-01{BACKUP_EXTENSION}")
        self.assertTrue(name.startswith("AUTO_BEFORE_RESTORE_"))
        self.assertTrue(name.endswith(BACKUP_EXTENSION))

    def test_safety_backup_created_before_restore(self) -> None:
        safety_file = storage_module.storage_service.backups_dir / (
            f"AUTO_BEFORE_RESTORE_test{BACKUP_EXTENSION}"
        )
        safety_file.write_bytes(b"safety")
        create_result = MagicMock()
        create_result.path = str(safety_file)
        restore_result = MagicMock(
            workspace_root=Path("/ws"),
            database_integrity="ok",
            warnings=[],
            notes=[],
        )
        call_order: list[str] = []

        def fake_create(*_a, **_k):
            call_order.append("create")
            return create_result

        def fake_restore(*_a, **_k):
            call_order.append("restore")
            return restore_result

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=QDialog.DialogCode.Accepted,
                ):
                    with patch.object(wf_mod, "create_instance_backup", side_effect=fake_create):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                wf_mod, "restore_instance_backup", side_effect=fake_restore
                            ):
                                with patch.object(
                                    wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                ):
                                    with patch.object(wf_mod.QMessageBox, "information"):
                                        with patch.object(QApplication, "quit"):
                                            ok = self.service.restore_instance_backup_ui(
                                                self.parent
                                            )
        self.assertTrue(ok)
        self.assertEqual(call_order, ["create", "restore"])
        self.assertTrue(safety_file.is_file())

    def test_restore_not_started_when_safety_backup_fails(self) -> None:
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
                        ):
                            with patch.object(wf_mod, "restore_instance_backup") as mock_restore:
                                ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        mock_restore.assert_not_called()

    def test_safety_backup_kept_after_successful_restore(self) -> None:
        case_dir = _TMP / "keep-success"
        case_dir.mkdir(parents=True, exist_ok=True)
        ws, db, settings = _make_ws(case_dir, note="current")
        package = case_dir / f"to-restore{BACKUP_EXTENSION}"
        create_instance_backup(
            package,
            workspace_root=ws,
            database_path=db,
            settings_path=settings,
        )
        (ws / "prilohy" / "a.txt").write_text("changed-before-restore", encoding="utf-8")

        safety = storage_module.storage_service.backups_dir / (
            f"AUTO_BEFORE_RESTORE_kept{BACKUP_EXTENSION}"
        )
        safety.write_bytes(b"safety-keep")

        from core.backup import restore_instance_backup

        restore_instance_backup(
            package,
            workspace_root=ws,
            settings_path=settings,
        )
        self.assertTrue(safety.is_file())
        self.assertEqual(safety.read_bytes(), b"safety-keep")

    def test_safety_backup_kept_after_failed_restore(self) -> None:
        safety_file = storage_module.storage_service.backups_dir / (
            f"AUTO_BEFORE_RESTORE_failkeep{BACKUP_EXTENSION}"
        )
        safety_file.write_bytes(b"keep-me")
        create_result = MagicMock(path=str(safety_file))

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
                        wf_mod, "create_instance_backup", return_value=create_result
                    ):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                wf_mod,
                                "restore_instance_backup",
                                side_effect=InstanceRestoreError(
                                    RESTORE_ERR_FAILED_BEFORE_SWAP,
                                    "selhání",
                                ),
                            ):
                                with patch.object(
                                    wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                ):
                                    ok = self.service.restore_instance_backup_ui(self.parent)
        self.assertFalse(ok)
        self.assertTrue(safety_file.is_file())

    def test_normal_backup_filename_unchanged(self) -> None:
        from core.backup import default_instance_backup_filename

        name = default_instance_backup_filename("2026-07-30_221501")
        self.assertEqual(name, f"manazer-bozp-instance-2026-07-30_221501{BACKUP_EXTENSION}")
        self.assertFalse(name.startswith("AUTO_BEFORE_RESTORE_"))


if __name__ == "__main__":
    unittest.main()
