"""AUDIT-METHOD-LONG-OPERATION-4B: responsivní ukládání editoru metodiky."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-method-long-op-4b-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import initialize_database  # noqa: E402

initialize_database()

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from core.services.editable_catalog_service import editable_catalog_service  # noqa: E402
from core.widgets.long_operation_runner import (  # noqa: E402
    LongOperationCancelled,
    LongOperationContext,
)
from moduly.audity.constants import (  # noqa: E402
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    KNOWLEDGE_EDITOR_SAVED_MESSAGE,
    KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (  # noqa: E402
    AssertionQuestionKindChange,
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service  # noqa: E402
from moduly.audity.sluzby.audit_method_save_operation import (  # noqa: E402
    AUDIT_METHOD_SAVE_RELOAD_FAILED_TEXT,
    PHASE_BACKUP,
    PHASE_PREPARE,
    PHASE_SAVE,
    PHASE_VALIDATE,
    AuditMethodSaveError,
    AuditMethodSaveSnapshot,
    persist_audit_method_save,
)
from moduly.audity.sluzby.audit_method_v2_backup_service import (  # noqa: E402
    AuditMethodV2BackupError,
    allocate_pre_v2_backup_path,
    list_pre_v2_backups,
    pre_v2_backup_exists,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind  # noqa: E402
from moduly.audity.sluzby.system_audit_workplace_service import (  # noqa: E402
    system_audit_workplace_service,
)
from moduly.audity.ui.audity_knowledge_editor_dialog import (  # noqa: E402
    AudityKnowledgeEditorDialog,
)
from moduly.nastaveni.sluzby.settings_service import settings_service  # noqa: E402
from tests.audit_method_save_wait import wait_for_audit_method_save  # noqa: E402

_PROCESS_URAZY = "urazy_mimo_udalosti"
_SECTION_URAZY = "evidence_hlaseni_urazu"
_ASSERTION_URAZY = "vsechny_urazy_evidovany"
_COL_KIND = 2


def _stub_pre_v2_backup():
    def fake_ensure(**_kwargs):
        if pre_v2_backup_exists():
            return None
        target = allocate_pre_v2_backup_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MBBACKUP-STUB")
        return target

    return patch(
        "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
        side_effect=fake_ensure,
    )


def _knowledge_path(filename: str) -> Path:
    return audit_knowledge_service.audity_dir / filename


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _assertion_kind(path: Path, section_id: str, assertion_id: str) -> str:
    payload = _load_json(path)
    for section in payload.get("sekce") or []:
        if section.get("id") != section_id:
            continue
        for item in section.get("auditni_tvrzeni") or []:
            if item.get("id") == assertion_id:
                return interpret_question_kind(item.get("question_kind"))
    raise AssertionError(f"{assertion_id} not found")


def _kind_combo(dialog: AudityKnowledgeEditorDialog, assertion_id: str) -> QComboBox:
    widget = dialog.section_editor._assertions_widget
    for row in range(widget._table.rowCount()):
        combo = widget._table.cellWidget(row, _COL_KIND)
        if isinstance(combo, QComboBox) and combo.property("assertion_id") == assertion_id:
            return combo
    raise AssertionError(f"combo for {assertion_id} not found")


class _FakeCtx:
    def __init__(self) -> None:
        self.phases: list[tuple[str, bool, bool]] = []
        self.progress: list[tuple[int, int]] = []
        self._atomic = False
        self.cancel = False

    def set_phase(self, text, *, indeterminate=False, atomic=False):
        self._atomic = bool(atomic)
        self.phases.append((str(text), bool(indeterminate), bool(atomic)))

    def set_progress(self, current, total):
        self.progress.append((int(current), int(total)))

    def set_status(self, text):
        return None

    def is_cancel_requested(self) -> bool:
        return self.cancel and not self._atomic

    def check_cancel(self) -> None:
        if self.is_cancel_requested():
            raise LongOperationCancelled()


class _SignalLog:
    def __init__(self, signal) -> None:
        self.items: list[tuple] = []
        self._signal = signal
        signal.connect(self._on)

    def _on(self, *args) -> None:
        self.items.append(args)

    @property
    def count(self) -> int:
        return len(self.items)

    def wait(self, timeout_ms: int = 8000) -> None:
        if self.items:
            return
        loop = QEventLoop()

        def _quit(*_args) -> None:
            loop.quit()

        self._signal.connect(_quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        self._signal.disconnect(_quit)
        timer.stop()
        if not self.items:
            raise AssertionError("Očekávaný signál nedorazil.")


def _snapshot_kinds(*changes: AssertionQuestionKindChange) -> AuditMethodSaveSnapshot:
    return AuditMethodSaveSnapshot(
        system_workplace_pending=False,
        system_workplace_id=None,
        question_kind_changes=changes,
        process_drafts=(),
        section_drafts=(),
        selected_process_id=_PROCESS_URAZY,
        selected_section_id=_SECTION_URAZY,
    )


class PersistServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = _knowledge_path("urazy_mimo_udalosti.json")
        self._original = _load_json(self._path)
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()
        for backup in list_pre_v2_backups():
            backup.unlink(missing_ok=True)

    def tearDown(self) -> None:
        self._backup_patcher.stop()
        _write_json(self._path, self._original)

    def test_batch_kinds_one_write_per_file(self) -> None:
        payload = _load_json(self._path)
        section = next(item for item in payload["sekce"] if item["id"] == _SECTION_URAZY)
        added_ids = []
        for index in range(100):
            item = dict(section["auditni_tvrzeni"][0])
            item["id"] = f"batch4b_{index:03d}"
            item["text"] = f"4B otázka {index}"
            item.pop("question_kind", None)
            section["auditni_tvrzeni"].append(item)
            added_ids.append(item["id"])
        _write_json(self._path, payload)

        changes = tuple(
            AssertionQuestionKindChange(
                process_id=_PROCESS_URAZY,
                section_id=_SECTION_URAZY,
                assertion_id=assertion_id,
                question_kind=(
                    AUDIT_QUESTION_KIND_SYSTEM
                    if index % 2 == 0
                    else AUDIT_QUESTION_KIND_OPERATION
                ),
            )
            for index, assertion_id in enumerate(added_ids)
        )
        writes = {"n": 0}
        loads = {"n": 0}
        original_write = audit_knowledge_editor_service.atomic_write_json
        original_load = audit_knowledge_editor_service.load_json_safe

        def counting_write(path, data):
            writes["n"] += 1
            original_write(path, data)

        def counting_load(path):
            if path.name == "urazy_mimo_udalosti.json":
                loads["n"] += 1
            return original_load(path)

        ctx = _FakeCtx()
        with (
            patch.object(
                audit_knowledge_editor_service,
                "atomic_write_json",
                side_effect=counting_write,
            ),
            patch.object(
                audit_knowledge_editor_service,
                "load_json_safe",
                side_effect=counting_load,
            ),
        ):
            started = time.perf_counter()
            result = persist_audit_method_save(ctx, _snapshot_kinds(*changes))
            elapsed = time.perf_counter() - started
        self.assertEqual(writes["n"], 1)
        self.assertEqual(loads["n"], 1)
        self.assertEqual(result.saved_question_kinds, 100)
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, added_ids[0]),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        print(f"LONG-OP-4B persist 100 druhů: {elapsed:.3f}s", flush=True)
        phase_texts = [item[0] for item in ctx.phases]
        self.assertIn(PHASE_PREPARE, phase_texts)
        self.assertIn(PHASE_VALIDATE, phase_texts)
        self.assertIn(PHASE_SAVE, phase_texts)
        self.assertTrue(any(atomic for _text, _ind, atomic in ctx.phases))

    def test_cancel_before_atomic_writes_nothing(self) -> None:
        before = self._path.read_text(encoding="utf-8")
        ctx = _FakeCtx()
        ctx.cancel = True
        with self.assertRaises(LongOperationCancelled):
            persist_audit_method_save(
                ctx,
                _snapshot_kinds(
                    AssertionQuestionKindChange(
                        process_id=_PROCESS_URAZY,
                        section_id=_SECTION_URAZY,
                        assertion_id=_ASSERTION_URAZY,
                        question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                    )
                ),
            )
        self.assertEqual(self._path.read_text(encoding="utf-8"), before)

    def test_pre_v2_failure_keeps_json(self) -> None:
        before = self._path.read_text(encoding="utf-8")
        ctx = _FakeCtx()
        with patch(
            "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
            side_effect=AuditMethodV2BackupError("záloha selhala"),
        ):
            with self.assertRaises(AuditMethodSaveError) as raised:
                persist_audit_method_save(
                    ctx,
                    _snapshot_kinds(
                        AssertionQuestionKindChange(
                            process_id=_PROCESS_URAZY,
                            section_id=_SECTION_URAZY,
                            assertion_id=_ASSERTION_URAZY,
                            question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                        )
                    ),
                )
        self.assertIn("záloha selhala", str(raised.exception))
        self.assertEqual(self._path.read_text(encoding="utf-8"), before)

    def test_write_failure_keeps_pending_semantics(self) -> None:
        before = self._path.read_text(encoding="utf-8")
        ctx = _FakeCtx()
        with patch.object(
            audit_knowledge_editor_service,
            "atomic_write_json",
            side_effect=OSError("zápis selhal"),
        ):
            with self.assertRaises(AuditMethodSaveError):
                persist_audit_method_save(
                    ctx,
                    _snapshot_kinds(
                        AssertionQuestionKindChange(
                            process_id=_PROCESS_URAZY,
                            section_id=_SECTION_URAZY,
                            assertion_id=_ASSERTION_URAZY,
                            question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                        )
                    ),
                )
        self.assertEqual(self._path.read_text(encoding="utf-8"), before)

    def test_process_and_section_metadata(self) -> None:
        ctx = _FakeCtx()
        snapshot = AuditMethodSaveSnapshot(
            system_workplace_pending=False,
            system_workplace_id=None,
            question_kind_changes=(),
            process_drafts=(
                (
                    _PROCESS_URAZY,
                    {
                        "nazev": "4B proces",
                        "popis": "p",
                        "ucel_procesu": "",
                        "proc_je_dulezity": "",
                        "ocekavany_vystup": "",
                        "poradi": 1,
                        "aktivni": True,
                    },
                ),
            ),
            section_drafts=(
                (
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    {
                        "nazev": "4B oblast",
                        "popis": "s",
                        "cil_overeni": "c",
                        "poradi": 1,
                        "aktivni": True,
                    },
                ),
            ),
            selected_process_id=_PROCESS_URAZY,
            selected_section_id=_SECTION_URAZY,
        )
        result = persist_audit_method_save(ctx, snapshot)
        payload = _load_json(self._path)
        self.assertEqual(payload.get("nazev"), "4B proces")
        section = next(item for item in payload["sekce"] if item["id"] == _SECTION_URAZY)
        self.assertEqual(section.get("nazev"), "4B oblast")
        self.assertEqual(result.saved_process_ids, (_PROCESS_URAZY,))
        self.assertEqual(result.saved_section_keys, ((_PROCESS_URAZY, _SECTION_URAZY),))
        self.assertIsInstance(result.unclassified_count, int)

    def test_post_validation_failure_raises(self) -> None:
        ctx = _FakeCtx()
        original = audit_knowledge_editor_service.validate_user_file
        calls = {"n": 0}

        def failing(relative_path, data=None):
            if data is None:
                calls["n"] += 1
                if calls["n"] >= 1:
                    return ["simulovaná post-validace"]
            return original(relative_path, data)

        before = self._path.read_text(encoding="utf-8")
        with patch.object(
            audit_knowledge_editor_service,
            "validate_user_file",
            side_effect=failing,
        ):
            with self.assertRaises(AuditMethodSaveError) as raised:
                persist_audit_method_save(
                    ctx,
                    _snapshot_kinds(
                        AssertionQuestionKindChange(
                            process_id=_PROCESS_URAZY,
                            section_id=_SECTION_URAZY,
                            assertion_id=_ASSERTION_URAZY,
                            question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                        )
                    ),
                )
        self.assertIn("post-validace", str(raised.exception))
        self.assertIn("validac", str(raised.exception).lower())
        # Rollback v dávce obnoví původní JSON.
        restored = _load_json(self._path)
        original = json.loads(before)
        self.assertEqual(
            interpret_question_kind(
                next(
                    item
                    for section in restored["sekce"]
                    if section["id"] == _SECTION_URAZY
                    for item in section["auditni_tvrzeni"]
                    if item["id"] == _ASSERTION_URAZY
                ).get("question_kind")
            ),
            interpret_question_kind(
                next(
                    item
                    for section in original["sekce"]
                    if section["id"] == _SECTION_URAZY
                    for item in section["auditni_tvrzeni"]
                    if item["id"] == _ASSERTION_URAZY
                ).get("question_kind")
            ),
        )

    def test_rollback_failure_is_reported(self) -> None:
        ctx = _FakeCtx()
        original_copy = __import__("shutil").copy2
        original_validate = audit_knowledge_editor_service.validate_user_file

        def failing_validate(relative_path, data=None):
            if data is None:
                return ["simulovaná post-validace"]
            return original_validate(relative_path, data)

        def failing_copy(src, dst, *args, **kwargs):
            if str(dst).endswith("urazy_mimo_udalosti.json"):
                raise OSError("obnova selhala")
            return original_copy(src, dst, *args, **kwargs)

        with (
            patch.object(
                audit_knowledge_editor_service,
                "validate_user_file",
                side_effect=failing_validate,
            ),
            patch(
                "moduly.audity.sluzby.audit_knowledge_editor_service.shutil.copy2",
                side_effect=failing_copy,
            ),
        ):
            with self.assertRaises(AuditMethodSaveError) as raised:
                persist_audit_method_save(
                    ctx,
                    _snapshot_kinds(
                        AssertionQuestionKindChange(
                            process_id=_PROCESS_URAZY,
                            section_id=_SECTION_URAZY,
                            assertion_id=_ASSERTION_URAZY,
                            question_kind=AUDIT_QUESTION_KIND_SYSTEM,
                        )
                    ),
                )
        text = str(raised.exception)
        self.assertIn("post-validace", text)
        self.assertIn("obnova selhala", text)


class EditorLongOperationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = _knowledge_path("urazy_mimo_udalosti.json")
        self._original = _load_json(self._path)
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()
        system_audit_workplace_service.settings_path().unlink(missing_ok=True)

    def tearDown(self) -> None:
        self._backup_patcher.stop()
        _write_json(self._path, self._original)
        system_audit_workplace_service.settings_path().unlink(missing_ok=True)

    def _open_section(self) -> AudityKnowledgeEditorDialog:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(
            dialog.knowledge_tree.select_node(_PROCESS_URAZY, _SECTION_URAZY)
        )
        return dialog

    def test_three_actions_use_one_persist_function(self) -> None:
        calls: list[str] = []
        original = persist_audit_method_save

        def wrapped(ctx, snapshot):
            calls.append(threading.current_thread().name)
            return original(ctx, snapshot)

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
            side_effect=wrapped,
        ):
            dialog = self._open_section()
            _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
                _kind_combo(dialog, _ASSERTION_URAZY).findData(
                    AUDIT_QUESTION_KIND_SYSTEM
                )
            )
            gui_ident = threading.get_ident()
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
            self.assertEqual(len(calls), 1)
            self.assertIsNotNone(dialog._save_result)
            self.assertNotEqual(dialog._save_result.worker_thread_ident, gui_ident)
            snapshot = dialog._build_save_snapshot()
            self.assertEqual(snapshot.snapshot_thread_ident, gui_ident)
            dialog.section_editor.discard_pending_assertion_kinds()
            dialog.close()

            dialog = self._open_section()
            _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
                _kind_combo(dialog, _ASSERTION_URAZY).findData(
                    AUDIT_QUESTION_KIND_OPERATION
                )
            )
            dialog._save_and_close()
            wait_for_audit_method_save(dialog)
            self.assertEqual(len(calls), 2)

            dialog = self._open_section()
            _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
                _kind_combo(dialog, _ASSERTION_URAZY).findData(
                    AUDIT_QUESTION_KIND_SYSTEM
                )
            )
            with patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
                return_value="save",
            ):
                self.assertFalse(dialog._confirm_close())
            wait_for_audit_method_save(dialog)
            self.assertEqual(len(calls), 3)

    def test_snapshot_has_no_qt_objects(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        snapshot = dialog._build_save_snapshot()
        self.assertIsInstance(snapshot, AuditMethodSaveSnapshot)
        self.assertTrue(snapshot.question_kind_changes)
        from PySide6.QtWidgets import QWidget

        self.assertFalse(isinstance(snapshot, QWidget))
        self.assertFalse(any(isinstance(item, QWidget) for item in snapshot.question_kind_changes))
        dialog.section_editor.discard_pending_assertion_kinds()
        dialog.close()

    def test_repeat_click_does_not_start_second_save(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        starts = {"n": 0}
        original_start = dialog._save_runner.start

        def counting_start(*args, **kwargs):
            starts["n"] += 1
            return original_start(*args, **kwargs)

        with patch.object(dialog._save_runner, "start", side_effect=counting_start):
            dialog._save_busy = True
            dialog._apply_changes()
            dialog._save_and_close()
        self.assertEqual(starts["n"], 0)
        dialog._save_busy = False
        dialog.section_editor.discard_pending_assertion_kinds()
        dialog.close()

    def test_no_changes_skips_worker(self) -> None:
        dialog = self._open_section()
        starts = {"n": 0}
        original_start = dialog._save_runner.start

        def counting_start(*args, **kwargs):
            starts["n"] += 1
            return original_start(*args, **kwargs)

        with patch.object(dialog._save_runner, "start", side_effect=counting_start):
            dialog._apply_changes()
        self.assertEqual(starts["n"], 0)
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        dialog.close()

    def test_apply_keeps_dialog_open_and_restores_once(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        reloads = {"n": 0}
        original_reload = dialog.knowledge_tree.reload_tree

        def counting_reload(*args, **kwargs):
            reloads["n"] += 1
            return original_reload(*args, **kwargs)

        with patch.object(
            dialog.knowledge_tree, "reload_tree", side_effect=counting_reload
        ):
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
        self.assertEqual(reloads["n"], 1)
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)
        self.assertFalse(dialog.section_editor.has_pending_assertion_kinds())
        self.assertFalse(dialog._has_unsaved_changes())
        self.assertEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        self.assertEqual(
            dialog._unclassified_count_label.text(),
            KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL.format(
                count=dialog._save_result.unclassified_count
            ),
        )
        self.assertEqual(
            dialog.knowledge_tree.currentItem().data(
                0, dialog.knowledge_tree._ROLE_NODE_ID
            ),
            _SECTION_URAZY,
        )
        dialog.close()

    def test_save_and_close_waits_for_thread_cleanup(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(
                AUDIT_QUESTION_KIND_OPERATION
            )
        )
        order: list[str] = []
        original_accept = dialog.accept

        def tracking_accept():
            self.assertFalse(dialog._save_runner.is_running())
            order.append("accept")
            original_accept()

        with patch.object(dialog, "accept", side_effect=tracking_accept):
            dialog._save_and_close()
            wait_for_audit_method_save(dialog)
        self.assertEqual(order, ["accept"])
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_fast_save_does_not_flash_progress(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        started = time.perf_counter()
        dialog._apply_changes()
        wait_for_audit_method_save(dialog)
        elapsed = time.perf_counter() - started
        progress = dialog._save_progress
        self.assertIsNotNone(progress)
        self.assertFalse(progress.was_presented())
        print(f"LONG-OP-4B rychlé uložení: {elapsed:.3f}s", flush=True)
        dialog.close()

    def test_slow_save_shows_phase_and_stays_responsive(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        original = persist_audit_method_save
        entered = threading.Event()
        proceed = threading.Event()
        seen_phase = {"text": ""}

        def slow(ctx: LongOperationContext, snapshot):
            ctx.set_phase(PHASE_VALIDATE, indeterminate=True, atomic=False)
            entered.set()
            proceed.wait(timeout=5)
            return original(ctx, snapshot)

        pinged = {"ok": False}

        def ping():
            pinged["ok"] = True

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
            side_effect=slow,
        ):
            dialog._progress_delay_ms = 0  # type: ignore[attr-defined]
            progress = dialog._ensure_save_progress_dialog()
            progress._delay_ms = 0
            phases = _SignalLog(dialog._save_runner.phase_changed)
            dialog._apply_changes()
            self.assertTrue(entered.wait(timeout=5))
            QTimer.singleShot(0, ping)
            deadline = time.perf_counter() + 2
            while not pinged["ok"] and time.perf_counter() < deadline:
                self._app.processEvents()
            self.assertTrue(pinged["ok"])
            if phases.items:
                seen_phase["text"] = phases.items[0][0]
            proceed.set()
            wait_for_audit_method_save(dialog)
        self.assertTrue(progress.was_presented() or seen_phase["text"])
        dialog.close()

    def test_first_pre_v2_backup_is_atomic(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        original = persist_audit_method_save
        entered = threading.Event()
        proceed = threading.Event()
        atomic_seen = {"ok": False}

        def gated(ctx: LongOperationContext, snapshot):
            ctx.set_phase(PHASE_BACKUP, indeterminate=True, atomic=True)
            atomic_seen["ok"] = True
            entered.set()
            proceed.wait(timeout=5)
            return original(ctx, snapshot)

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
            side_effect=gated,
        ):
            progress = dialog._ensure_save_progress_dialog()
            progress._delay_ms = 0
            dialog._apply_changes()
            try:
                self.assertTrue(entered.wait(timeout=5))
                deadline = time.perf_counter() + 2
                while not dialog._save_runner.is_atomic() and time.perf_counter() < deadline:
                    self._app.processEvents()
                self.assertTrue(dialog._save_runner.is_atomic())
                dialog._save_runner.request_cancel()
                self.assertTrue(dialog._save_runner.is_atomic())
                event = QCloseEvent()
                progress.closeEvent(event)
                self.assertFalse(event.isAccepted())
            finally:
                proceed.set()
                wait_for_audit_method_save(dialog)
        self.assertTrue(atomic_seen["ok"])
        dialog.close()

    def test_cancel_before_atomic_keeps_dirty(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        original = persist_audit_method_save
        entered = threading.Event()
        proceed = threading.Event()

        def gated(ctx: LongOperationContext, snapshot):
            ctx.set_phase(PHASE_PREPARE, indeterminate=True, atomic=False)
            entered.set()
            while not ctx.is_cancel_requested():
                if proceed.wait(0.05):
                    break
            ctx.check_cancel()
            return original(ctx, snapshot)

        before = self._path.read_text(encoding="utf-8")
        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
            side_effect=gated,
        ):
            dialog._apply_changes()
            try:
                self.assertTrue(entered.wait(timeout=5))
                dialog._save_runner.request_cancel()
                proceed.set()
                wait_for_audit_method_save(dialog)
            finally:
                proceed.set()
        self.assertEqual(self._path.read_text(encoding="utf-8"), before)
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertNotEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        dialog.section_editor.discard_pending_assertion_kinds()
        dialog.close()

    def test_persist_error_keeps_dirty_and_allows_retry(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
                side_effect=AuditMethodSaveError("zápis selhal"),
            ),
            patch.object(dialog, "_warn") as warning,
        ):
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
        warning.assert_called()
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertNotEqual(dialog._status_label.text(), KNOWLEDGE_EDITOR_SAVED_MESSAGE)
        dialog._apply_changes()
        wait_for_audit_method_save(dialog)
        self.assertFalse(dialog._has_unsaved_changes())
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        dialog.close()

    def test_reload_failure_after_successful_write(self) -> None:
        dialog = self._open_section()
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        progress = dialog._ensure_save_progress_dialog()
        progress._delay_ms = 60_000
        warned: list[str] = []
        dialog._warn = warned.append
        with patch.object(
            dialog.knowledge_tree,
            "reload_tree",
            side_effect=RuntimeError("reload boom"),
        ):
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        self.assertTrue(dialog._reload_failed_after_save)
        self.assertFalse(dialog._apply_btn.isEnabled())
        self.assertEqual(warned, [AUDIT_METHOD_SAVE_RELOAD_FAILED_TEXT])
        self.assertNotIn("neulož", warned[0].lower())
        dialog._apply_changes()
        self.assertTrue(dialog._reload_failed_after_save)
        dialog.section_editor.discard_pending_assertion_kinds()
        dialog.close()

    def test_system_workplace_saves_in_worker(self) -> None:
        workplace = settings_service.save_workplace(name="4B systém", active=True)
        dialog = AudityKnowledgeEditorDialog()
        index = dialog._system_workplace_combo.findData(workplace.id)
        self.assertGreaterEqual(index, 0)
        dialog._system_workplace_combo.setCurrentIndex(index)
        threads: list[int] = []
        original = system_audit_workplace_service.persist_saved_system_workplace_id

        def tracking(workplace_id):
            threads.append(threading.get_ident())
            return original(workplace_id)

        with patch.object(
            system_audit_workplace_service,
            "persist_saved_system_workplace_id",
            side_effect=tracking,
        ):
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
        self.assertEqual(
            system_audit_workplace_service.get_system_audit_workplace_id(),
            workplace.id,
        )
        self.assertTrue(threads)
        self.assertNotEqual(threads[0], threading.get_ident())
        dialog.close()

    def test_multiple_drafts_and_kinds_one_persist(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_URAZY))
        dialog.process_editor._nazev_edit.setText("4B draft proces")
        self.assertTrue(
            dialog.knowledge_tree.select_node(_PROCESS_URAZY, _SECTION_URAZY)
        )
        dialog.section_editor._nazev_edit.setText("4B draft oblast")
        _kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            _kind_combo(dialog, _ASSERTION_URAZY).findData(AUDIT_QUESTION_KIND_SYSTEM)
        )
        persist_calls = {"n": 0}
        original = persist_audit_method_save

        def counting(ctx, snapshot):
            persist_calls["n"] += 1
            self.assertTrue(snapshot.process_drafts)
            self.assertTrue(snapshot.section_drafts)
            self.assertTrue(snapshot.question_kind_changes)
            return original(ctx, snapshot)

        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.persist_audit_method_save",
            side_effect=counting,
        ):
            dialog._apply_changes()
            wait_for_audit_method_save(dialog)
        self.assertEqual(persist_calls["n"], 1)
        payload = _load_json(self._path)
        self.assertEqual(payload.get("nazev"), "4B draft proces")
        section = next(item for item in payload["sekce"] if item["id"] == _SECTION_URAZY)
        self.assertEqual(section.get("nazev"), "4B draft oblast")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
