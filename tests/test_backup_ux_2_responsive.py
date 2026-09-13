"""BACKUP-UX-2: responzivní UI při obnově ze zálohy."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="mbbackup-ux-2-resp-"))

with patch.object(Path, "home", return_value=_TMP):
    from PySide6.QtCore import QThread, QTimer, Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication, QMessageBox

    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.backup import (
        BACKUP_EXTENSION,
        INTEGRITY_VALID,
        RESTORE_ERR_FAILED_BEFORE_SWAP,
        InstanceBackupError,
        InstanceRestoreError,
        create_instance_backup,
        restore_instance_backup,
    )
    from core.backup.package_integrity import BackupIntegrityReport
    from core.database.database_initializer import initialize_database
    from core.widgets.long_operation_dialog import LongOperationDialog

    initialize_database()

    from moduly.sprava_dat.sluzby import instance_backup_restore_operation as restore_op_mod
    from moduly.sprava_dat.sluzby import instance_backup_workflow_service as wf_mod
    from moduly.sprava_dat.sluzby.instance_backup_restore_operation import (
        BACKUP_RESTORE_PROGRESS_PHASE,
        BACKUP_RESTORE_PROGRESS_TITLE,
        InstanceBackupRestoreSnapshot,
        create_safety_backup_work,
        restore_instance_backup_work,
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


def _make_workspace(root: Path, note: str = "záloha") -> tuple[Path, Path, Path]:
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


def _valid_report() -> BackupIntegrityReport:
    meta = MagicMock(created_at="2026-07-01T12:00:00+00:00", app_version="3.2.0")
    return BackupIntegrityReport(status=INTEGRITY_VALID, issues=[], metadata=meta)


def _fake_safety(path: Path) -> MagicMock:
    return MagicMock(path=str(path))


def _fake_restore_result() -> MagicMock:
    return MagicMock(
        workspace_root=Path("/ws"),
        database_integrity="ok",
        warnings=[],
        notes=[],
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


class BackupUx2ResponsiveTestCase(unittest.TestCase):
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

    def _run_restore(
        self,
        *,
        create_side_effect,
        restore_side_effect,
    ) -> bool:
        safety_target = storage_module.storage_service.backups_dir / f"AUTO{BACKUP_EXTENSION}"
        patches = [
            patch.object(
                wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
            ),
            patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()),
            patch.object(
                wf_mod.RestoreConfirmDialog,
                "exec",
                return_value=wf_mod.RestoreConfirmDialog.DialogCode.Accepted,
            ),
            patch.object(
                restore_op_mod, "create_instance_backup", side_effect=create_side_effect
            ),
            patch.object(
                restore_op_mod, "restore_instance_backup", side_effect=restore_side_effect
            ),
            patch("core.database.session.dispose_database_engine"),
            patch.object(wf_mod.MessageWithDetailsDialog, "exec", return_value=1),
            patch.object(wf_mod.QMessageBox, "information"),
            patch.object(wf_mod.QMessageBox, "warning"),
            patch.object(QApplication, "quit"),
        ]
        for p in patches:
            p.start()
        try:
            _ = safety_target
            return self.service.restore_instance_backup_ui(self.parent)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_a_long_restore_does_not_block_event_loop(self) -> None:
        gui_thread = QThread.currentThread()
        entered = threading.Event()
        proceed = threading.Event()
        ticks: list[int] = []
        seen: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            seen["thread"] = QThread.currentThread()
            entered.set()
            proceed.wait(timeout=5)
            return _fake_restore_result()

        def on_tick() -> None:
            ticks.append(len(ticks) + 1)
            if len(ticks) >= 4 and entered.is_set():
                proceed.set()

        timer = QTimer(self.parent)
        timer.setInterval(15)
        timer.timeout.connect(on_tick)
        timer.start()
        try:
            ok = self._run_restore(
                create_side_effect=fake_create,
                restore_side_effect=fake_restore,
            )
        finally:
            timer.stop()
            proceed.set()

        self.assertTrue(ok)
        self.assertGreaterEqual(len(ticks), 4)
        self.assertIn("thread", seen)
        self.assertIsNot(seen["thread"], gui_thread)

    def test_b_and_c_modal_busy_dialog_cannot_be_dismissed(self) -> None:
        entered = threading.Event()
        proceed = threading.Event()
        captured: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            entered.set()
            proceed.wait(timeout=5)
            return _fake_restore_result()

        def inspect_dialog() -> None:
            if not entered.wait(timeout=2):
                proceed.set()
                return
            dialog = self.service._restore_progress_dialog
            self.assertIsNotNone(dialog)
            assert dialog is not None
            QApplication.sendPostedEvents()
            self._app.processEvents()
            captured["visible"] = dialog.isVisible()
            captured["title"] = dialog.windowTitle()
            captured["modal"] = dialog.isModal()
            captured["modality"] = dialog.windowModality()
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
            ok = self._run_restore(
                create_side_effect=fake_create,
                restore_side_effect=fake_restore,
            )
        finally:
            proceed.set()

        self.assertTrue(ok)
        self.assertTrue(captured.get("visible"))
        self.assertEqual(captured.get("title"), BACKUP_RESTORE_PROGRESS_TITLE)
        self.assertTrue(captured.get("modal"))
        self.assertEqual(captured.get("modality"), Qt.WindowModality.WindowModal)
        self.assertIn("Probíhá obnova dat ze zálohy.", str(captured.get("phase")))
        self.assertIn("chvíli trvat", str(captured.get("phase")))
        self.assertEqual(captured.get("bar_max"), 0)
        self.assertFalse(captured.get("cancel_visible"))
        self.assertFalse(captured.get("close_accepted"))
        self.assertTrue(captured.get("still_visible"))
        self.assertTrue(captured.get("after_escape"))
        self.assertIsNone(self.service._restore_progress_dialog)
        self.assertFalse(self.service._operation_running)

    def test_d_worker_does_not_touch_qt_widgets(self) -> None:
        source = Path(restore_op_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("QWidget", source)
        self.assertNotIn("QDialog", source)
        self.assertNotIn("QLabel", source)
        self.assertNotIn("QProgressBar", source)
        self.assertNotIn("QFileDialog", source)
        self.assertNotIn("QMessageBox", source)
        self.assertNotIn("QApplication", source)
        self.assertNotIn("get_session", source)
        self.assertNotIn("SessionLocal", source)
        self.assertNotIn("set_progress", source)
        self.assertNotIn("dispose_database_engine", source)
        signature = inspect.signature(restore_instance_backup_work)
        self.assertIn("ctx", signature.parameters)
        self.assertIn("snapshot", signature.parameters)
        safety_sig = inspect.signature(create_safety_backup_work)
        self.assertIn("ctx", safety_sig.parameters)
        self.assertIn("snapshot", safety_sig.parameters)

    def test_e_db_lifecycle_stays_on_gui_thread(self) -> None:
        restore_fn = inspect.getsource(
            wf_mod.InstanceBackupWorkflowService.restore_instance_backup_ui
        )
        dispose_idx = restore_fn.index("dispose_database_engine")
        restore_work_idx = restore_fn.index("restore_instance_backup_work")
        self.assertLess(dispose_idx, restore_work_idx)
        self.assertIn("create_safety_backup_work", restore_fn)
        worker_source = Path(restore_op_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("get_session", worker_source)
        self.assertNotIn("SessionLocal", worker_source)

        gui_thread = QThread.currentThread()
        seen: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            return _fake_restore_result()

        def fake_dispose() -> None:
            seen["dispose_thread"] = QThread.currentThread()

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=wf_mod.RestoreConfirmDialog.DialogCode.Accepted,
                ):
                    with patch.object(
                        restore_op_mod, "create_instance_backup", side_effect=fake_create
                    ):
                        with patch(
                            "core.database.session.dispose_database_engine",
                            side_effect=fake_dispose,
                        ):
                            with patch.object(
                                restore_op_mod,
                                "restore_instance_backup",
                                side_effect=fake_restore,
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
        self.assertIs(seen.get("dispose_thread"), gui_thread)

    def test_f_safety_backup_before_restore_is_kept(self) -> None:
        order: list[str] = []

        def fake_create(*_args, **_kwargs):
            order.append("create")
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            order.append("restore")
            return _fake_restore_result()

        ok = self._run_restore(
            create_side_effect=fake_create,
            restore_side_effect=fake_restore,
        )
        self.assertTrue(ok)
        self.assertEqual(order, ["create", "restore"])
        restore_fn = inspect.getsource(
            wf_mod.InstanceBackupWorkflowService.restore_instance_backup_ui
        )
        self.assertIn("auto_before_restore_backup_filename", restore_fn)
        self.assertIn("create_safety_backup_work", restore_fn)

        ctx = _DummyCtx()
        target = storage_module.storage_service.backups_dir / f"AUTO_BEFORE_RESTORE_x{BACKUP_EXTENSION}"
        snapshot = InstanceBackupRestoreSnapshot(
            package_path="/ok.mbbackup",
            workspace_root=str(storage_module.storage_service.base),
            database_path=str(storage_module.storage_service.database_path),
            safety_target_path=str(target),
        )
        with patch.object(
            restore_op_mod,
            "create_instance_backup",
            return_value=_fake_safety(target),
        ) as mock_create:
            outcome = create_safety_backup_work(ctx, snapshot)
        self.assertEqual(outcome.safety_path, str(target.resolve()))
        mock_create.assert_called_once()
        self.assertEqual(ctx.phases[0][0], BACKUP_RESTORE_PROGRESS_PHASE)
        self.assertTrue(ctx.phases[0][1])
        self.assertTrue(ctx.phases[0][2])

    def test_g_safety_backup_error_stops_restore(self) -> None:
        restore_calls: list[str] = []

        def fake_create(*_args, **_kwargs):
            raise InstanceBackupError("disk full")

        def fake_restore(*_args, **_kwargs):
            restore_calls.append("restore")
            return _fake_restore_result()

        ok = self._run_restore(
            create_side_effect=fake_create,
            restore_side_effect=fake_restore,
        )
        self.assertFalse(ok)
        self.assertEqual(restore_calls, [])
        self.assertFalse(self.service._operation_running)
        self.assertIsNone(self.service._restore_progress_dialog)

    def test_h_successful_restore_matches_direct_api(self) -> None:
        case = _TMP / "real-h"
        src_ws, src_db, src_settings = _make_workspace(case / "src", note="from-backup")
        package = case / f"pkg{BACKUP_EXTENSION}"
        create_instance_backup(
            package,
            workspace_root=src_ws,
            database_path=src_db,
            settings_path=src_settings,
        )

        dest_direct, _, dest_direct_settings = _make_workspace(case / "dest-direct", note="old-d")
        dest_worker, dest_worker_db, dest_worker_settings = _make_workspace(
            case / "dest-worker", note="old-w"
        )

        direct = restore_instance_backup(
            package,
            workspace_root=dest_direct,
            settings_path=dest_direct_settings,
        )
        ctx = _DummyCtx()
        snapshot = InstanceBackupRestoreSnapshot(
            package_path=str(package),
            workspace_root=str(dest_worker.resolve()),
            database_path=str(dest_worker_db.resolve()),
            settings_path=str(dest_worker_settings.resolve()),
        )
        worker = restore_instance_backup_work(ctx, snapshot)
        self.assertIsNone(worker.restore_error)
        self.assertIsNone(worker.unexpected_error)
        self.assertIsNotNone(worker.restore_result)
        self.assertEqual(direct.database_integrity, worker.restore_result.database_integrity)
        self.assertEqual(
            (dest_direct / "prilohy" / "a.txt").read_text(encoding="utf-8"),
            (dest_worker / "prilohy" / "a.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            dest_direct_settings.read_text(encoding="utf-8"),
            dest_worker_settings.read_text(encoding="utf-8"),
        )
        self.assertEqual(ctx.phases[0][0], BACKUP_RESTORE_PROGRESS_PHASE)

        shown: dict[str, str] = {}
        original_init = wf_mod.MessageWithDetailsDialog.__init__

        def tracking_init(self_dlg, parent, *, title, message, details="", level="info"):
            shown["title"] = title
            shown["message"] = message
            return original_init(
                self_dlg,
                parent,
                title=title,
                message=message,
                details=details,
                level=level,
            )

        quit_mock = MagicMock()
        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=wf_mod.RestoreConfirmDialog.DialogCode.Accepted,
                ):
                    with patch.object(
                        restore_op_mod,
                        "create_instance_backup",
                        return_value=_fake_safety(
                            storage_module.storage_service.backups_dir / "AUTO.mbbackup"
                        ),
                    ):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                restore_op_mod,
                                "restore_instance_backup",
                                return_value=_fake_restore_result(),
                            ):
                                with patch.object(
                                    wf_mod.MessageWithDetailsDialog, "__init__", tracking_init
                                ):
                                    with patch.object(
                                        wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                    ):
                                        with patch.object(wf_mod.QMessageBox, "information"):
                                            with patch.object(QApplication, "quit", quit_mock):
                                                ok = self.service.restore_instance_backup_ui(
                                                    self.parent
                                                )
        self.assertTrue(ok)
        self.assertEqual(shown.get("title"), "Obnova dokončena")
        self.assertIn("úspěšně obnovena", shown.get("message", ""))
        quit_mock.assert_called_once()

    def test_i_restore_error_does_not_report_success_or_block_gui(self) -> None:
        shown: dict[str, str] = {}
        original_init = wf_mod.MessageWithDetailsDialog.__init__

        def tracking_init(self_dlg, parent, *, title, message, details="", level="info"):
            shown["title"] = title
            shown["message"] = message
            shown["level"] = level
            return original_init(
                self_dlg,
                parent,
                title=title,
                message=message,
                details=details,
                level=level,
            )

        def fake_create(*_args, **_kwargs):
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            raise InstanceRestoreError(RESTORE_ERR_FAILED_BEFORE_SWAP, "selhání")

        with patch.object(
            wf_mod.QFileDialog, "getOpenFileName", return_value=("/ok.mbbackup", "")
        ):
            with patch.object(wf_mod, "inspect_backup_integrity", return_value=_valid_report()):
                with patch.object(
                    wf_mod.RestoreConfirmDialog,
                    "exec",
                    return_value=wf_mod.RestoreConfirmDialog.DialogCode.Accepted,
                ):
                    with patch.object(
                        restore_op_mod, "create_instance_backup", side_effect=fake_create
                    ):
                        with patch("core.database.session.dispose_database_engine"):
                            with patch.object(
                                restore_op_mod,
                                "restore_instance_backup",
                                side_effect=fake_restore,
                            ):
                                with patch.object(
                                    wf_mod.MessageWithDetailsDialog, "__init__", tracking_init
                                ):
                                    with patch.object(
                                        wf_mod.MessageWithDetailsDialog, "exec", return_value=1
                                    ):
                                        with patch.object(QApplication, "quit") as quit_mock:
                                            ok = self.service.restore_instance_backup_ui(
                                                self.parent
                                            )
                                            quit_mock.assert_not_called()
        self.assertFalse(ok)
        self.assertEqual(shown.get("title"), "Obnova ze zálohy")
        self.assertNotEqual(shown.get("title"), "Obnova dokončena")
        self.assertIn("nebyla změněna", shown.get("message", ""))
        self.assertFalse(self.service._operation_running)
        self.assertIsNone(self.service._restore_progress_dialog)
        self.assertTrue(self.parent.create_mbbackup_button.isEnabled())
        self.assertTrue(self.parent.restore_mbbackup_button.isEnabled())

    def test_j_cannot_start_concurrent_backup_or_restore(self) -> None:
        entered = threading.Event()
        proceed = threading.Event()
        second: dict[str, object] = {}

        def fake_create(*_args, **_kwargs):
            return _fake_safety(storage_module.storage_service.backups_dir / "AUTO.mbbackup")

        def fake_restore(*_args, **_kwargs):
            entered.set()
            proceed.wait(timeout=5)
            return _fake_restore_result()

        def try_second() -> None:
            if not entered.wait(timeout=2):
                proceed.set()
                return
            second["running"] = self.service._operation_running
            second["create_ok"] = self.service.create_instance_backup_ui(self.parent)
            second["restore_ok"] = self.service.restore_instance_backup_ui(self.parent)
            second["create_enabled"] = self.parent.create_mbbackup_button.isEnabled()
            second["restore_enabled"] = self.parent.restore_mbbackup_button.isEnabled()
            proceed.set()

        timer = QTimer(self.parent)
        timer.setSingleShot(True)
        timer.timeout.connect(try_second)
        timer.start(20)
        try:
            ok = self._run_restore(
                create_side_effect=fake_create,
                restore_side_effect=fake_restore,
            )
        finally:
            proceed.set()

        self.assertTrue(ok)
        self.assertTrue(second.get("running"))
        self.assertFalse(second.get("create_ok"))
        self.assertFalse(second.get("restore_ok"))
        self.assertFalse(second.get("create_enabled"))
        self.assertFalse(second.get("restore_enabled"))
        self.assertFalse(self.service._operation_running)
        self.assertTrue(self.parent.create_mbbackup_button.isEnabled())

    def test_k_backup_list_paths_and_format_unchanged(self) -> None:
        restore_fn = inspect.getsource(
            wf_mod.InstanceBackupWorkflowService.restore_instance_backup_ui
        )
        backup_tab_source = Path(
            inspect.getfile(BackupTab)
        ).read_text(encoding="utf-8")
        self.assertIn("storage_service.backups_dir", restore_fn)
        self.assertIn("BACKUP_EXTENSION", restore_fn)
        self.assertIn("inspect_backup_integrity", restore_fn)
        self.assertIn("getOpenFileName", restore_fn)
        self.assertIn("Vybrat zálohu k obnově", restore_fn)
        self.assertNotIn("refresh_backup_list", restore_fn)
        self.assertNotIn("last_backup", restore_fn)
        self.assertIn("self.refresh()", backup_tab_source)
        self.assertIn("_update_recovery_status", backup_tab_source)
        self.assertNotIn("QApplication.processEvents", restore_fn)
        self.assertNotIn("BackupProgressDialog", restore_fn)
        self.assertIn("LongOperationDialog", restore_fn)
        self.assertIn("delay_ms=0", restore_fn)
        self.assertIn("allow_cancel=False", restore_fn)

        constructed: list[str] = []
        original_bp = BackupProgressDialog.__init__

        def tracking_bp(self_dlg, *args, **kwargs):
            constructed.append("progress")
            return original_bp(self_dlg, *args, **kwargs)

        with patch.object(BackupProgressDialog, "__init__", tracking_bp):
            ok = self._run_restore(
                create_side_effect=lambda *_a, **_k: _fake_safety(
                    storage_module.storage_service.backups_dir / "AUTO.mbbackup"
                ),
                restore_side_effect=lambda *_a, **_k: _fake_restore_result(),
            )
        self.assertTrue(ok)
        self.assertEqual(constructed, [])


if __name__ == "__main__":
    unittest.main()
