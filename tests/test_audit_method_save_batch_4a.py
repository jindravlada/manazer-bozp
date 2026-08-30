"""AUDIT-METHOD-SAVE-BATCH-4A: dávkové ukládání druhů otázek."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-method-save-batch-4a-"))
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

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from core.services.editable_catalog_service import editable_catalog_service  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (  # noqa: E402
    AssertionQuestionKindChange,
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service  # noqa: E402
from moduly.audity.sluzby.audit_method_v2_backup_service import (  # noqa: E402
    allocate_pre_v2_backup_path,
    list_pre_v2_backups,
    pre_v2_backup_exists,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind  # noqa: E402
from moduly.audity.ui.audity_knowledge_editor_dialog import (  # noqa: E402
    AudityKnowledgeEditorDialog,
)
from tests.audit_method_save_wait import wait_for_audit_method_save  # noqa: E402

_PROCESS_URAZY = "urazy_mimo_udalosti"
_SECTION_URAZY = "evidence_hlaseni_urazu"
_ASSERTION_URAZY = "vsechny_urazy_evidovany"
_PROCESS_PLAN = "planovani_bozp"
_SECTION_PLAN = "cile_politika"
_ASSERTION_PLAN = "meritelne_cile"
_PROCESS_RISKS = "rizeni_rizik"
_SECTION_RISKS = "identifikace_nebezpeci"
_ASSERTION_RISKS = "id_proces_identifikace"
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


def _change(
    process_id: str,
    section_id: str,
    assertion_id: str,
    kind: str,
) -> AssertionQuestionKindChange:
    return AssertionQuestionKindChange(
        process_id=process_id,
        section_id=section_id,
        assertion_id=assertion_id,
        question_kind=kind,
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
    raise AssertionError(f"{assertion_id} not found in {path.name}")


def _find_assertion(path: Path, section_id: str, assertion_id: str) -> dict:
    payload = _load_json(path)
    for section in payload.get("sekce") or []:
        if section.get("id") != section_id:
            continue
        for item in section.get("auditni_tvrzeni") or []:
            if item.get("id") == assertion_id:
                return item
    raise AssertionError(f"{assertion_id} not found")


def _bak_count(filename: str) -> int:
    backup_dir = audit_knowledge_editor_service.backup_dir()
    if not backup_dir.is_dir():
        return 0
    return len(list(backup_dir.glob(f"{filename}.*.bak")))


class _CallCounter:
    def __init__(self) -> None:
        self.ensure = 0
        self.load_target = 0
        self.prev2 = 0
        self.backup = 0
        self.write = 0
        self.post = 0


class SaveBatchServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()

    def setUp(self) -> None:
        self._paths = {
            name: _knowledge_path(name)
            for name in (
                "urazy_mimo_udalosti.json",
                "planovani_bozp.json",
                "rizeni_rizik.json",
            )
        }
        self._originals = {name: _load_json(path) for name, path in self._paths.items()}
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()

    def tearDown(self) -> None:
        self._backup_patcher.stop()
        for name, original in self._originals.items():
            _write_json(self._paths[name], original)

    def _urazy(self) -> Path:
        return self._paths["urazy_mimo_udalosti.json"]

    def test_single_change(self) -> None:
        errors = audit_knowledge_editor_service.set_assertion_question_kind(
            _PROCESS_URAZY,
            _SECTION_URAZY,
            _ASSERTION_URAZY,
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            _assertion_kind(self._urazy(), _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )

    def test_system_and_operation_mix(self) -> None:
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    AUDIT_QUESTION_KIND_SYSTEM,
                ),
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    "urazy_klasifikovany",
                    AUDIT_QUESTION_KIND_OPERATION,
                ),
            ]
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            _assertion_kind(self._urazy(), _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        self.assertEqual(
            _assertion_kind(self._urazy(), _SECTION_URAZY, "urazy_klasifikovany"),
            AUDIT_QUESTION_KIND_OPERATION,
        )

    def test_legacy_missing_kind_can_be_classified(self) -> None:
        item = _find_assertion(self._urazy(), _SECTION_URAZY, _ASSERTION_URAZY)
        self.assertNotIn("question_kind", item)
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    AUDIT_QUESTION_KIND_OPERATION,
                )
            ]
        )
        self.assertEqual(errors, [])
        stored = _find_assertion(self._urazy(), _SECTION_URAZY, _ASSERTION_URAZY)
        self.assertEqual(stored["question_kind"], AUDIT_QUESTION_KIND_OPERATION)

    def test_noop_does_not_write(self) -> None:
        audit_knowledge_editor_service.set_assertion_question_kind(
            _PROCESS_URAZY,
            _SECTION_URAZY,
            _ASSERTION_URAZY,
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        before = self._urazy().read_text(encoding="utf-8")
        bak_before = _bak_count("urazy_mimo_udalosti.json")
        with patch.object(
            audit_knowledge_editor_service, "atomic_write_json"
        ) as write:
            with patch(
                "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup"
            ) as prev2:
                errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                    [
                        _change(
                            _PROCESS_URAZY,
                            _SECTION_URAZY,
                            _ASSERTION_URAZY,
                            AUDIT_QUESTION_KIND_SYSTEM,
                        )
                    ]
                )
        self.assertEqual(errors, [])
        write.assert_not_called()
        prev2.assert_not_called()
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)
        self.assertEqual(_bak_count("urazy_mimo_udalosti.json"), bak_before)

    def test_duplicate_same_change_is_unified(self) -> None:
        counter = _CallCounter()
        svc = audit_knowledge_editor_service
        original_write = svc.atomic_write_json

        def write(path, data):
            counter.write += 1
            original_write(path, data)

        with patch.object(svc, "atomic_write_json", side_effect=write):
            errors = svc.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                ]
            )
        self.assertEqual(errors, [])
        self.assertEqual(counter.write, 1)

    def test_conflicting_duplicate_rejects_batch(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    AUDIT_QUESTION_KIND_SYSTEM,
                ),
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    AUDIT_QUESTION_KIND_OPERATION,
                ),
            ]
        )
        self.assertTrue(errors)
        self.assertIn("Konfliktní dávka", "\n".join(errors))
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_missing_assertion_rejects_batch(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    "neexistuje_tvrzeni_xyz",
                    AUDIT_QUESTION_KIND_SYSTEM,
                )
            ]
        )
        self.assertTrue(errors)
        self.assertIn("nebylo nalezeno", "\n".join(errors))
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_invalid_kind_rejects_batch(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    "future",
                )
            ]
        )
        self.assertTrue(errors)
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_preserves_unrelated_fields_and_order(self) -> None:
        payload = _load_json(self._urazy())
        section = next(
            item for item in payload["sekce"] if item["id"] == _SECTION_URAZY
        )
        before_ids = [item["id"] for item in section["auditni_tvrzeni"]]
        original_popis = section["auditni_tvrzeni"][0]["popis"]
        section["auditni_tvrzeni"][0]["poznamka_batch"] = "ponechat"
        extra = dict(section["auditni_tvrzeni"][0])
        extra["id"] = "zachovat_poradi_batch"
        extra["text"] = "Pořadí se nesmí změnit."
        extra["poradi"] = 999
        extra.pop("poznamka_batch", None)
        section["auditni_tvrzeni"].append(extra)
        _write_json(self._urazy(), payload)

        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            [
                _change(
                    _PROCESS_URAZY,
                    _SECTION_URAZY,
                    _ASSERTION_URAZY,
                    AUDIT_QUESTION_KIND_SYSTEM,
                )
            ]
        )
        self.assertEqual(errors, [])
        after = _load_json(self._urazy())
        section_after = next(
            item for item in after["sekce"] if item["id"] == _SECTION_URAZY
        )
        after_ids = [item["id"] for item in section_after["auditni_tvrzeni"]]
        self.assertEqual(after_ids, before_ids + ["zachovat_poradi_batch"])
        stored = section_after["auditni_tvrzeni"][0]
        self.assertEqual(stored["poznamka_batch"], "ponechat")
        self.assertEqual(stored["popis"], original_popis)
        self.assertEqual(stored["zavaznost"], "vysoka")
        self.assertEqual(stored["question_kind"], AUDIT_QUESTION_KIND_SYSTEM)

    def test_one_hundred_changes_one_file_io_contract(self) -> None:
        payload = _load_json(self._urazy())
        section = next(
            item for item in payload["sekce"] if item["id"] == _SECTION_URAZY
        )
        template = dict(section["auditni_tvrzeni"][0])
        added_ids = []
        for index in range(100):
            item = dict(template)
            item["id"] = f"batch_kind_{index:03d}"
            item["text"] = f"Dávková otázka {index}"
            item.pop("question_kind", None)
            section["auditni_tvrzeni"].append(item)
            added_ids.append(item["id"])
        _write_json(self._urazy(), payload)

        changes = [
            _change(
                _PROCESS_URAZY,
                _SECTION_URAZY,
                assertion_id,
                AUDIT_QUESTION_KIND_SYSTEM
                if index % 2 == 0
                else AUDIT_QUESTION_KIND_OPERATION,
            )
            for index, assertion_id in enumerate(added_ids)
        ]
        counter = _CallCounter()
        svc = audit_knowledge_editor_service
        original_ensure = svc.ensure_user_catalogs
        original_load = svc.load_json_safe
        original_backup = svc.backup_file
        original_write = svc.atomic_write_json
        original_validate = svc.validate_user_file
        original_prev2 = self._backup_patcher.kwargs["side_effect"]

        def ensure():
            counter.ensure += 1
            original_ensure()

        def load(path):
            if path.name == "urazy_mimo_udalosti.json":
                counter.load_target += 1
            return original_load(path)

        def backup(path):
            counter.backup += 1
            return original_backup(path)

        def write(path, data):
            counter.write += 1
            original_write(path, data)

        def validate(relative_path, data=None):
            if data is None:
                counter.post += 1
            return original_validate(relative_path, data)

        def prev2(**kwargs):
            counter.prev2 += 1
            return original_prev2(**kwargs)

        with (
            patch.object(svc, "ensure_user_catalogs", side_effect=ensure),
            patch.object(svc, "load_json_safe", side_effect=load),
            patch.object(svc, "backup_file", side_effect=backup),
            patch.object(svc, "atomic_write_json", side_effect=write),
            patch.object(svc, "validate_user_file", side_effect=validate),
            patch(
                "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
                side_effect=prev2,
            ),
        ):
            started = time.perf_counter()
            errors = svc.set_assertion_question_kinds_batch(changes)
            batch_seconds = time.perf_counter() - started
        self.assertEqual(errors, [])
        self.assertEqual(counter.ensure, 1)
        self.assertEqual(counter.load_target, 1)
        self.assertEqual(counter.prev2, 1)
        self.assertEqual(counter.backup, 1)
        self.assertEqual(counter.write, 1)
        self.assertEqual(counter.post, 1)
        self.assertEqual(
            _assertion_kind(self._urazy(), _SECTION_URAZY, added_ids[0]),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        self.assertEqual(
            _assertion_kind(self._urazy(), _SECTION_URAZY, added_ids[1]),
            AUDIT_QUESTION_KIND_OPERATION,
        )
        print(f"BATCH-4A 100 změn v 1 souboru: {batch_seconds:.3f}s", flush=True)

        sample = changes[:10]
        payload = _load_json(self._urazy())
        section = next(
            item for item in payload["sekce"] if item["id"] == _SECTION_URAZY
        )
        sample_ids = {item.assertion_id for item in sample}
        for item in section["auditni_tvrzeni"]:
            if str(item.get("id") or "") in sample_ids:
                item.pop("question_kind", None)
        _write_json(self._urazy(), payload)
        write_calls = {"n": 0}
        original_write = svc.atomic_write_json

        def counting_write(path, data):
            write_calls["n"] += 1
            original_write(path, data)

        with patch.object(svc, "atomic_write_json", side_effect=counting_write):
            started = time.perf_counter()
            for change in sample:
                errors = svc.set_assertion_question_kind(
                    change.process_id,
                    change.section_id,
                    change.assertion_id,
                    change.question_kind,
                )
                self.assertEqual(errors, [])
            individual_seconds = time.perf_counter() - started
        self.assertEqual(write_calls["n"], 10)
        print(
            f"BATCH-4A 10× jednotlivě: {individual_seconds:.3f}s "
            f"(dávka 100 změn {batch_seconds:.3f}s)",
            flush=True,
        )
        self.assertLess(batch_seconds, individual_seconds)

    def test_three_files_io_contract(self) -> None:
        changes = [
            _change(
                _PROCESS_URAZY,
                _SECTION_URAZY,
                _ASSERTION_URAZY,
                AUDIT_QUESTION_KIND_SYSTEM,
            ),
            _change(
                _PROCESS_PLAN,
                _SECTION_PLAN,
                _ASSERTION_PLAN,
                AUDIT_QUESTION_KIND_OPERATION,
            ),
            _change(
                _PROCESS_RISKS,
                _SECTION_RISKS,
                _ASSERTION_RISKS,
                AUDIT_QUESTION_KIND_SYSTEM,
            ),
        ]
        counter = _CallCounter()
        svc = audit_knowledge_editor_service
        original_ensure = svc.ensure_user_catalogs
        original_load = svc.load_json_safe
        original_backup = svc.backup_file
        original_write = svc.atomic_write_json
        loaded: list[str] = []
        written: list[str] = []

        def ensure():
            counter.ensure += 1
            original_ensure()

        def load(path):
            if path.name != "procesy.json":
                counter.load_target += 1
                loaded.append(path.name)
            return original_load(path)

        def backup(path):
            counter.backup += 1
            return original_backup(path)

        def write(path, data):
            counter.write += 1
            written.append(path.name)
            original_write(path, data)

        with (
            patch.object(svc, "ensure_user_catalogs", side_effect=ensure),
            patch.object(svc, "load_json_safe", side_effect=load),
            patch.object(svc, "backup_file", side_effect=backup),
            patch.object(svc, "atomic_write_json", side_effect=write),
        ):
            errors = svc.set_assertion_question_kinds_batch(changes)
        self.assertEqual(errors, [])
        self.assertEqual(counter.ensure, 1)
        self.assertEqual(counter.load_target, 3)
        self.assertEqual(sorted(loaded), sorted(set(loaded)))
        self.assertEqual(counter.backup, 3)
        self.assertEqual(counter.write, 3)
        self.assertEqual(len(set(written)), 3)

    def test_pre_v2_runs_once_before_write(self) -> None:
        for backup in list_pre_v2_backups():
            backup.unlink(missing_ok=True)
        order: list[str] = []
        svc = audit_knowledge_editor_service
        original_write = svc.atomic_write_json
        original_prev2 = self._backup_patcher.kwargs["side_effect"]

        def prev2(**kwargs):
            order.append("prev2")
            return original_prev2(**kwargs)

        def write(path, data):
            order.append("write")
            original_write(path, data)

        with (
            patch(
                "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
                side_effect=prev2,
            ),
            patch.object(svc, "atomic_write_json", side_effect=write),
        ):
            errors = svc.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    )
                ]
            )
        self.assertEqual(errors, [])
        self.assertEqual(order[0], "prev2")
        self.assertIn("write", order)
        self.assertEqual(order.count("prev2"), 1)

        with patch(
            "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
            side_effect=prev2,
        ):
            errors = svc.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        "urazy_klasifikovany",
                        AUDIT_QUESTION_KIND_OPERATION,
                    )
                ]
            )
        self.assertEqual(errors, [])
        self.assertEqual(order.count("prev2"), 2)

    def test_pre_v2_failure_does_not_change_json(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            AuditMethodV2BackupError,
        )

        with patch(
            "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
            side_effect=AuditMethodV2BackupError("záloha selhala"),
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    )
                ]
            )
        self.assertTrue(errors)
        self.assertIn("záloha selhala", "\n".join(errors))
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_pre_validation_failure_writes_nothing(self) -> None:
        before = {
            name: path.read_text(encoding="utf-8")
            for name, path in self._paths.items()
        }
        original = audit_knowledge_editor_service.validate_user_file

        def failing(relative_path, data=None):
            if data is not None:
                return ["simulovaná pre-validace"]
            return original(relative_path, data)

        with patch.object(
            audit_knowledge_editor_service,
            "validate_user_file",
            side_effect=failing,
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                    _change(
                        _PROCESS_PLAN,
                        _SECTION_PLAN,
                        _ASSERTION_PLAN,
                        AUDIT_QUESTION_KIND_OPERATION,
                    ),
                ]
            )
        self.assertTrue(errors)
        for name, path in self._paths.items():
            self.assertEqual(path.read_text(encoding="utf-8"), before[name])

    def test_first_write_failure_keeps_json(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        with patch.object(
            audit_knowledge_editor_service,
            "atomic_write_json",
            side_effect=OSError("první zápis"),
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    )
                ]
            )
        self.assertTrue(errors)
        self.assertIn("první zápis", "\n".join(errors))
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_second_write_failure_rolls_back_first(self) -> None:
        before = {
            name: path.read_text(encoding="utf-8")
            for name, path in self._paths.items()
        }
        original_write = audit_knowledge_editor_service.atomic_write_json
        calls = {"n": 0}

        def failing_write(path, data):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("druhý zápis")
            original_write(path, data)

        with patch.object(
            audit_knowledge_editor_service,
            "atomic_write_json",
            side_effect=failing_write,
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                    _change(
                        _PROCESS_PLAN,
                        _SECTION_PLAN,
                        _ASSERTION_PLAN,
                        AUDIT_QUESTION_KIND_OPERATION,
                    ),
                    _change(
                        _PROCESS_RISKS,
                        _SECTION_RISKS,
                        _ASSERTION_RISKS,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                ]
            )
        self.assertTrue(errors)
        self.assertIn("druhý zápis", "\n".join(errors))
        for name, path in self._paths.items():
            self.assertEqual(path.read_text(encoding="utf-8"), before[name])

    def test_post_validation_failure_rolls_back(self) -> None:
        before = self._urazy().read_text(encoding="utf-8")
        original = audit_knowledge_editor_service.validate_user_file

        def failing(relative_path, data=None):
            if data is None:
                return ["simulovaná post-validace"]
            return original(relative_path, data)

        with patch.object(
            audit_knowledge_editor_service,
            "validate_user_file",
            side_effect=failing,
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    )
                ]
            )
        self.assertTrue(errors)
        self.assertIn("post-validace", "\n".join(errors))
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), before)

    def test_rollback_error_is_reported_with_original(self) -> None:
        original_copy = shutil.copy2
        backup_root = audit_knowledge_editor_service.backup_dir()

        def selective_copy(src, dst, *args, **kwargs):
            dest = Path(dst)
            try:
                dest.resolve().relative_to(backup_root.resolve())
            except ValueError:
                raise OSError("obnova selhala") from None
            return original_copy(src, dst, *args, **kwargs)

        original_write = audit_knowledge_editor_service.atomic_write_json
        calls = {"n": 0}

        def failing_write(path, data):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("druhý zápis")
            original_write(path, data)

        with (
            patch.object(
                audit_knowledge_editor_service,
                "atomic_write_json",
                side_effect=failing_write,
            ),
            patch(
                "moduly.audity.sluzby.audit_knowledge_editor_service.shutil.copy2",
                side_effect=selective_copy,
            ),
        ):
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                [
                    _change(
                        _PROCESS_URAZY,
                        _SECTION_URAZY,
                        _ASSERTION_URAZY,
                        AUDIT_QUESTION_KIND_SYSTEM,
                    ),
                    _change(
                        _PROCESS_PLAN,
                        _SECTION_PLAN,
                        _ASSERTION_PLAN,
                        AUDIT_QUESTION_KIND_OPERATION,
                    ),
                ]
            )
        text = "\n".join(errors)
        self.assertIn("druhý zápis", text)
        self.assertIn("obnova selhala", text)

    def test_successful_batch_is_idempotent(self) -> None:
        changes = [
            _change(
                _PROCESS_URAZY,
                _SECTION_URAZY,
                _ASSERTION_URAZY,
                AUDIT_QUESTION_KIND_SYSTEM,
            )
        ]
        self.assertEqual(
            audit_knowledge_editor_service.set_assertion_question_kinds_batch(changes),
            [],
        )
        after_first = self._urazy().read_text(encoding="utf-8")
        with patch.object(
            audit_knowledge_editor_service, "atomic_write_json"
        ) as write:
            self.assertEqual(
                audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                    changes
                ),
                [],
            )
        write.assert_not_called()
        self.assertEqual(self._urazy().read_text(encoding="utf-8"), after_first)


class SaveBatchEditorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = _knowledge_path("urazy_mimo_udalosti.json")
        self._original = _load_json(self._path)
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()

    def tearDown(self) -> None:
        self._backup_patcher.stop()
        _write_json(self._path, self._original)

    def _open_section_dialog(self) -> AudityKnowledgeEditorDialog:
        dialog = AudityKnowledgeEditorDialog()
        self.assertTrue(
            dialog.knowledge_tree.select_node(_PROCESS_URAZY, _SECTION_URAZY)
        )
        self.assertTrue(dialog.section_editor.has_section())
        return dialog

    def _kind_combo(
        self, dialog: AudityKnowledgeEditorDialog, assertion_id: str
    ) -> QComboBox:
        widget = dialog.section_editor._assertions_widget
        for row in range(widget._table.rowCount()):
            combo = widget._table.cellWidget(row, _COL_KIND)
            if isinstance(combo, QComboBox) and combo.property("assertion_id") == assertion_id:
                return combo
        self.fail(f"combo for {assertion_id} not found")

    def test_flush_sends_one_batch_and_clears_pending(self) -> None:
        dialog = self._open_section_dialog()
        widget = dialog.section_editor._assertions_widget
        self._kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            self._kind_combo(dialog, _ASSERTION_URAZY).findData(
                AUDIT_QUESTION_KIND_SYSTEM
            )
        )
        self._kind_combo(dialog, "urazy_klasifikovany").setCurrentIndex(
            self._kind_combo(dialog, "urazy_klasifikovany").findData(
                AUDIT_QUESTION_KIND_OPERATION
            )
        )
        self.assertTrue(widget.has_pending_question_kinds())
        with (
            patch.object(
                audit_knowledge_editor_service,
                "set_assertion_question_kinds_batch",
                wraps=audit_knowledge_editor_service.set_assertion_question_kinds_batch,
            ) as batch,
            patch.object(
                audit_knowledge_editor_service,
                "set_assertion_question_kind",
                wraps=audit_knowledge_editor_service.set_assertion_question_kind,
            ) as single,
        ):
            self.assertTrue(dialog._flush_pending_assertion_kinds())
        self.assertEqual(batch.call_count, 1)
        self.assertEqual(len(batch.call_args.args[0]), 2)
        self.assertEqual(single.call_count, 0)
        self.assertFalse(widget.has_pending_question_kinds())
        dialog.close()

    def test_flush_error_keeps_pending_and_dirty(self) -> None:
        dialog = self._open_section_dialog()
        combo = self._kind_combo(dialog, _ASSERTION_URAZY)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        with patch.object(
            audit_knowledge_editor_service,
            "set_assertion_question_kinds_batch",
            return_value=["simulovaná chyba dávky"],
        ):
            errors = dialog.section_editor.flush_pending_assertion_kinds()
        self.assertEqual(errors, ["simulovaná chyba dávky"])
        self.assertTrue(dialog.section_editor.has_pending_assertion_kinds())
        self.assertTrue(dialog._has_unsaved_changes())
        dialog.section_editor.discard_pending_assertion_kinds()
        dialog.close()

    def test_apply_saves_all_pending_kinds(self) -> None:
        dialog = self._open_section_dialog()
        self._kind_combo(dialog, _ASSERTION_URAZY).setCurrentIndex(
            self._kind_combo(dialog, _ASSERTION_URAZY).findData(
                AUDIT_QUESTION_KIND_SYSTEM
            )
        )
        self._kind_combo(dialog, "urazy_klasifikovany").setCurrentIndex(
            self._kind_combo(dialog, "urazy_klasifikovany").findData(
                AUDIT_QUESTION_KIND_OPERATION
            )
        )
        dialog._apply_changes()
        wait_for_audit_method_save(dialog)
        self.assertFalse(dialog.section_editor.has_pending_assertion_kinds())
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, "urazy_klasifikovany"),
            AUDIT_QUESTION_KIND_OPERATION,
        )
        expected = audit_knowledge_service.count_unclassified_active_assertions(
            ensure=False
        )
        self.assertEqual(
            dialog._unclassified_count_label.text(),
            KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL.format(count=expected),
        )
        dialog.close()

    def test_save_and_close_uses_batch(self) -> None:
        dialog = self._open_section_dialog()
        combo = self._kind_combo(dialog, _ASSERTION_URAZY)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_OPERATION))
        with patch.object(
            audit_knowledge_editor_service,
            "set_assertion_question_kinds_batch",
            wraps=audit_knowledge_editor_service.set_assertion_question_kinds_batch,
        ) as batch:
            dialog._save_and_close()
            wait_for_audit_method_save(dialog)
        self.assertEqual(batch.call_count, 1)
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_OPERATION,
        )

    def test_close_save_option_uses_batch(self) -> None:
        dialog = self._open_section_dialog()
        combo = self._kind_combo(dialog, _ASSERTION_URAZY)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        with (
            patch(
                "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
                return_value="save",
            ),
            patch.object(
                audit_knowledge_editor_service,
                "set_assertion_question_kinds_batch",
                wraps=audit_knowledge_editor_service.set_assertion_question_kinds_batch,
            ) as batch,
        ):
            self.assertFalse(dialog._confirm_close())
            wait_for_audit_method_save(dialog)
        self.assertEqual(batch.call_count, 1)
        self.assertEqual(
            _assertion_kind(self._path, _SECTION_URAZY, _ASSERTION_URAZY),
            AUDIT_QUESTION_KIND_SYSTEM,
        )


if __name__ == "__main__":
    unittest.main()
