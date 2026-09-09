"""BACKUP-UX-1: responzivní UI při ručním vytvoření zálohy."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-ux-1-resp-"))

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import QThread, QTimer
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QMessageBox

    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.backup import (
        BACKUP_EXTENSION,
        BACKUP_FORMAT_VERSION,
        METADATA_FILENAME,
        PACKAGE_KIND_INSTANCE_BACKUP,
        PACKAGE_STATUS_COMPLETE,
        InstanceBackupError,
        create_instance_backup,
        verify_instance_backup_package,
    )
    from core.backup.package_create import PARTIAL_SUFFIX
    from core.database.database_initializer import initialize_database
    from core.database.upgrade_guard import create_verified_pre_migration_backup
    from core.widgets.long_operation_dialog import LongOperationDialog

    initialize_database()

    from moduly.sprava_dat.sluzby import instance_backup_create_operation as create_op_mod
    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_create_operation import (
        BACKUP_CREATE_PROGRESS_PHASE,
        BACKUP_CREATE_PROGRESS_TITLE,
        InstanceBackupCreateSnapshot,
        create_instance_backup_work,
    )
    from moduly.sprava_dat.sluzby.instance_backup_workflow_service import (
        InstanceBackupWorkflowService,
    )
    from moduly.sprava_dat.ui.backup_tab import BackupTab
    from moduly.sprava_dat.ui.instance_backup_dialogs import BackupProgressDialog


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_workspace(root: Path) -> tuple[Path, Path, Path]:
    workspace = root / "workspace"
    db_dir = workspace / "databaze"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "manager_bozp.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO demo(note) VALUES ('záloha')")
        conn.commit()
    finally:
        conn.close()
    for name in ("prilohy", "ciselniky", "templates", "konfigurace", "control_results"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    (workspace / "prilohy" / "a.txt").write_text("příloha", encoding="utf-8")
    (workspace / "ciselniky" / "c.json").write_text("{}", encoding="utf-8")
    (workspace / "templates" / "t.odt").write_bytes(b"PK")
    (workspace / "konfigurace" / "sprava_dat.json").write_text("{}", encoding="utf-8")
    settings = root / "settings.json"
    settings.write_text(json.dumps({"marker": "ux1"}), encoding="utf-8")
    return workspace, db_path, settings


def _fake_result(path: Path) -> MagicMock:
    meta = MagicMock()
    meta.created_at = "2026-09-09T12:00:00"
    meta.app_version = "3.2.0"
    meta.files = [1, 2]
    meta.format_version = 1
    meta.package_kind = PACKAGE_KIND_INSTANCE_BACKUP
    meta.total_content_size = 10
    meta.platform = "test"
    return MagicMock(
        path=path,
        metadata=meta,
        verified=True,
        database_integrity="ok",
        coverage_verdict="complete",
        unknown_workspace_roots=(),
    )


class _DummyCtx:
    def __init__(self) -> None:
        self.phases: list[tuple] = []
        self.statuses: list[str] = []

    def set_phase(self, text: str, *, indeterminate: bool = False, atomic: bool = False) -> None:
        self.phases.append((text, indeterminate, atomic))

    def set_progress(self, current: int, total: int) -> None:
        raise AssertionError("Worker nesmí předstírat procenta.")

    def set_status(self, text: str) -> None:
        self.statuses.append(str(text))

    def is_cancel_requested(self) -> bool:
        return False

    def check_cancel(self) -> None:
        return None


class BackupUx1ResponsiveTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _app()

    def setUp(self) -> None:
        with patch.object(Path, "home", return_value=_TMP):
            importlib.reload(storage_module)
            storage_module.storage_service.ensure_structure()
        wf_mod.storage_service = storage_module.storage_service
        self.service = InstanceBackupWorkflowService()
        self.parent = BackupTab()

    def _run_create(
        self,
        target: Path,
        *,
        create_side_effect,
    ) -> bool:
        patches = [
            patch.object(
                wf_mod.QFileDialog, "getSaveFileName", return_value=(str(target), "")
            ),
            patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1),
            patch.object(QMessageBox, "warning", return_value=0),
            patch.object(create_op_mod, "create_instance_backup", side_effect=create_side_effect),
        ]
        for p in patches:
            p.start()
        try:
            return self.service.create_instance_backup_ui(self.parent)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_a_manual_backup_runs_off_gui_thread(self) -> None:
        target = storage_module.storage_service.backups_dir / f"a{BACKUP_EXTENSION}"
        gui_thread = QThread.currentThread()
        seen: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            seen["thread"] = QThread.currentThread()
            return _fake_result(target)

        ok = self._run_create(target, create_side_effect=fake_create)
        self.assertTrue(ok)
        self.assertIn("thread", seen)
        self.assertIsNot(seen["thread"], gui_thread)

    def test_b_event_loop_stays_responsive_during_long_backup(self) -> None:
        target = storage_module.storage_service.backups_dir / f"b{BACKUP_EXTENSION}"
        entered = threading.Event()
        proceed = threading.Event()
        ticks: list[int] = []

        def fake_create(*_args, **_kwargs):
            entered.set()
            proceed.wait(timeout=5)
            return _fake_result(target)

        def on_tick() -> None:
            ticks.append(len(ticks) + 1)
            if len(ticks) >= 4 and entered.is_set():
                proceed.set()

        timer = QTimer(self.parent)
        timer.setInterval(15)
        timer.timeout.connect(on_tick)
        timer.start()
        try:
            ok = self._run_create(target, create_side_effect=fake_create)
        finally:
            timer.stop()
            proceed.set()

        self.assertTrue(ok)
        self.assertGreaterEqual(len(ticks), 4)

    def test_c_modal_busy_dialog_is_shown_and_cannot_be_dismissed(self) -> None:
        target = storage_module.storage_service.backups_dir / f"c{BACKUP_EXTENSION}"
        entered = threading.Event()
        proceed = threading.Event()
        captured: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            entered.set()
            proceed.wait(timeout=5)
            return _fake_result(target)

        def inspect_dialog() -> None:
            if not entered.wait(timeout=2):
                proceed.set()
                return
            dialog = self.service._create_progress_dialog
            self.assertIsNotNone(dialog)
            assert dialog is not None
            QApplication.sendPostedEvents()
            self._app.processEvents()
            captured["visible"] = dialog.isVisible()
            captured["title"] = dialog.windowTitle()
            captured["modal"] = dialog.isModal()
            captured["phase"] = dialog._phase_label.text()
            captured["bar_max"] = dialog._progress_bar.maximum()
            captured["cancel_visible"] = dialog._cancel_btn.isVisible()
            event = QCloseEvent()
            dialog.closeEvent(event)
            captured["close_accepted"] = event.isAccepted()
            captured["still_visible"] = dialog.isVisible()
            dialog.reject()
            captured["after_escape"] = dialog.isVisible()
            proceed.set()

        timer = QTimer(self.parent)
        timer.setSingleShot(True)
        timer.timeout.connect(inspect_dialog)
        timer.start(30)
        try:
            ok = self._run_create(target, create_side_effect=fake_create)
        finally:
            proceed.set()

        self.assertTrue(ok)
        self.assertTrue(captured.get("visible"))
        self.assertEqual(captured.get("title"), BACKUP_CREATE_PROGRESS_TITLE)
        self.assertTrue(captured.get("modal"))
        self.assertIn("Probíhá vytváření zálohy.", str(captured.get("phase")))
        self.assertIn("chvíli trvat", str(captured.get("phase")))
        self.assertEqual(captured.get("bar_max"), 0)
        self.assertFalse(captured.get("cancel_visible"))
        self.assertFalse(captured.get("close_accepted"))
        self.assertTrue(captured.get("still_visible"))
        self.assertTrue(captured.get("after_escape"))
        self.assertTrue(self.parent.create_mbbackup_button.isEnabled())
        self.assertIsNone(self.service._create_progress_dialog)

    def test_d_second_manual_backup_is_rejected_while_running(self) -> None:
        target = storage_module.storage_service.backups_dir / f"d{BACKUP_EXTENSION}"
        entered = threading.Event()
        proceed = threading.Event()
        second: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            entered.set()
            proceed.wait(timeout=5)
            return _fake_result(target)

        def try_second() -> None:
            if not entered.wait(timeout=2):
                proceed.set()
                return
            second["running"] = self.service._operation_running
            second["ok"] = self.service.create_instance_backup_ui(self.parent)
            proceed.set()

        timer = QTimer(self.parent)
        timer.setSingleShot(True)
        timer.timeout.connect(try_second)
        timer.start(20)
        try:
            ok = self._run_create(target, create_side_effect=fake_create)
        finally:
            proceed.set()

        self.assertTrue(ok)
        self.assertTrue(second.get("running"))
        self.assertFalse(second.get("ok"))
        self.assertFalse(self.service._operation_running)

    def test_e_success_closes_dialog_and_creates_valid_backup(self) -> None:
        workspace, db_path, settings = _make_workspace(_TMP / "real-e")
        target = storage_module.storage_service.backups_dir / f"e{BACKUP_EXTENSION}"

        def real_create(path, **kwargs):
            kwargs.pop("progress_callback", None)
            return create_instance_backup(
                path,
                workspace_root=workspace,
                database_path=db_path,
                settings_path=settings,
            )

        ok = self._run_create(target, create_side_effect=real_create)
        self.assertTrue(ok)
        self.assertTrue(target.is_file())
        self.assertFalse(target.with_name(target.name + PARTIAL_SUFFIX).exists())
        meta = verify_instance_backup_package(target)
        self.assertEqual(meta.package_kind, PACKAGE_KIND_INSTANCE_BACKUP)
        self.assertEqual(meta.format_version, BACKUP_FORMAT_VERSION)
        self.assertEqual(meta.package_status, PACKAGE_STATUS_COMPLETE)
        self.assertIsNone(self.service._create_progress_dialog)
        self.assertFalse(self.service._operation_running)
        self.assertTrue(self.parent.create_mbbackup_button.isEnabled())

    def test_f_error_closes_dialog_shows_error_and_app_stays_usable(self) -> None:
        target = storage_module.storage_service.backups_dir / f"f{BACKUP_EXTENSION}"

        def fail(*_args, **_kwargs):
            raise InstanceBackupError("Simulovaná chyba zálohy.")

        recorded: dict[str, str] = {}
        original_init = wf_mod.MessageWithDetailsDialog.__init__

        def tracking_init(self, parent, *, title, message, details="", level="info"):
            recorded["title"] = title
            recorded["message"] = message
            recorded["details"] = details
            return original_init(
                self,
                parent,
                title=title,
                message=message,
                details=details,
                level=level,
            )

        with patch.object(
            wf_mod.QFileDialog, "getSaveFileName", return_value=(str(target), "")
        ):
            with patch.object(create_op_mod, "create_instance_backup", side_effect=fail):
                with patch.object(wf_mod.MessageWithDetailsDialog, "__init__", tracking_init):
                    with patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1):
                        ok = self.service.create_instance_backup_ui(self.parent)

        self.assertFalse(ok)
        self.assertEqual(recorded.get("title"), "Vytvoření zálohy")
        self.assertEqual(recorded.get("message"), "Zálohu se nepodařilo vytvořit.")
        self.assertIn("Simulovaná chyba zálohy.", recorded.get("details", ""))
        self.assertIsNone(self.service._create_progress_dialog)
        self.assertFalse(self.service._operation_running)
        self.assertTrue(self.parent.create_mbbackup_button.isEnabled())
        self.assertFalse(target.exists())

        follow_target = storage_module.storage_service.backups_dir / f"f-ok{BACKUP_EXTENSION}"
        ok2 = self._run_create(
            follow_target,
            create_side_effect=lambda *_a, **_k: _fake_result(follow_target),
        )
        self.assertTrue(ok2)

    def test_g_worker_does_not_touch_qt_widgets(self) -> None:
        source = Path(create_op_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("QWidget", source)
        self.assertNotIn("QDialog", source)
        self.assertNotIn("QLabel", source)
        self.assertNotIn("QProgressBar", source)
        self.assertNotIn("QFileDialog", source)
        self.assertNotIn("QMessageBox", source)
        self.assertNotIn("get_session", source)
        self.assertNotIn("SessionLocal", source)
        self.assertNotIn("QApplication", source)
        self.assertNotIn("set_progress", source)
        signature = inspect.signature(create_instance_backup_work)
        self.assertIn("ctx", signature.parameters)
        self.assertIn("snapshot", signature.parameters)

    def test_h_automatic_backup_does_not_open_new_modal_dialog(self) -> None:
        wf_source = Path(wf_mod.__file__).read_text(encoding="utf-8")
        restore_fn = inspect.getsource(wf_mod.InstanceBackupWorkflowService.restore_instance_backup_ui)
        auto_fn = inspect.getsource(
            wf_mod.InstanceBackupWorkflowService._create_auto_before_restore_backup
        )
        self.assertIn("BackupProgressDialog", restore_fn)
        self.assertNotIn("LongOperationDialog", restore_fn)
        self.assertNotIn("LongOperationDialog", auto_fn)
        self.assertIn("create_instance_backup", auto_fn)
        self.assertNotIn("LongOperationDialog", inspect.getsource(create_verified_pre_migration_backup))

        constructed: list[str] = []
        original_init = LongOperationDialog.__init__

        def tracking_init(self, *args, **kwargs):
            constructed.append("long")
            return original_init(self, *args, **kwargs)

        target = storage_module.storage_service.backups_dir / f"h{BACKUP_EXTENSION}"
        with patch.object(LongOperationDialog, "__init__", tracking_init):
            with patch.object(
                wf_mod,
                "create_instance_backup",
                return_value=MagicMock(path=target),
            ):
                path = self.service._create_auto_before_restore_backup()
        self.assertEqual(Path(path), Path(target).resolve())
        self.assertEqual(constructed, [])

        backup_progress_calls: list[str] = []
        original_bp = BackupProgressDialog.__init__

        def tracking_bp(self, *args, **kwargs):
            backup_progress_calls.append(str(kwargs.get("title", "")))
            return original_bp(self, *args, **kwargs)

        with patch.object(BackupProgressDialog, "__init__", tracking_bp):
            with patch.object(
                wf_mod,
                "create_instance_backup",
                return_value=MagicMock(path=target),
            ):
                self.service._create_auto_before_restore_backup()
        self.assertEqual(backup_progress_calls, [])

    def test_i_backup_format_matches_direct_create(self) -> None:
        workspace, db_path, settings = _make_workspace(_TMP / "real-i")
        direct_target = _TMP / "real-i" / f"direct{BACKUP_EXTENSION}"
        worker_target = _TMP / "real-i" / f"worker{BACKUP_EXTENSION}"

        direct = create_instance_backup(
            direct_target,
            workspace_root=workspace,
            database_path=db_path,
            settings_path=settings,
        )
        ctx = _DummyCtx()
        snapshot = InstanceBackupCreateSnapshot(
            target_path=str(worker_target),
            workspace_root=str(workspace),
            database_path=str(db_path),
            settings_path=str(settings),
        )
        worker = create_instance_backup_work(ctx, snapshot)

        self.assertEqual(ctx.phases[0][0], BACKUP_CREATE_PROGRESS_PHASE)
        self.assertTrue(ctx.phases[0][1])
        self.assertTrue(ctx.phases[0][2])

        self.assertEqual(direct.metadata.package_kind, worker.metadata.package_kind)
        self.assertEqual(direct.metadata.format_version, worker.metadata.format_version)
        self.assertEqual(direct.metadata.package_status, PACKAGE_STATUS_COMPLETE)
        self.assertEqual(worker.metadata.package_status, PACKAGE_STATUS_COMPLETE)
        self.assertEqual(
            {entry.path for entry in direct.metadata.files},
            {entry.path for entry in worker.metadata.files},
        )
        self.assertEqual(
            {entry.sha256 for entry in direct.metadata.files},
            {entry.sha256 for entry in worker.metadata.files},
        )

        with zipfile.ZipFile(direct_target, "r") as zf_direct:
            with zipfile.ZipFile(worker_target, "r") as zf_worker:
                self.assertEqual(sorted(zf_direct.namelist()), sorted(zf_worker.namelist()))
                self.assertIn(METADATA_FILENAME, zf_direct.namelist())
                raw_direct = json.loads(zf_direct.read(METADATA_FILENAME).decode("utf-8"))
                raw_worker = json.loads(zf_worker.read(METADATA_FILENAME).decode("utf-8"))
        self.assertEqual(raw_direct["package_kind"], raw_worker["package_kind"])
        self.assertEqual(raw_direct["format_version"], raw_worker["format_version"])
        self.assertEqual(raw_direct["package_status"], raw_worker["package_status"])

    def test_create_uses_long_operation_runner_not_gui_create(self) -> None:
        source = inspect.getsource(
            wf_mod.InstanceBackupWorkflowService.create_instance_backup_ui
        )
        self.assertIn("LongOperationRunner", source)
        self.assertIn("LongOperationDialog", source)
        self.assertIn("allow_cancel=False", source)
        self.assertIn("create_instance_backup_work", source)
        self.assertNotIn("QApplication.processEvents", source)
        self.assertNotIn("BackupProgressDialog", source)


if __name__ == "__main__":
    unittest.main()
