"""AUDIT-METHOD-V2b: UI systémového provozu, druh otázky, pre-v2 záloha, start auditu."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-method-v2b-"))
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

from PySide6.QtWidgets import QApplication  # noqa: E402
from sqlalchemy import select  # noqa: E402

from core.database.session import get_session  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_GENERATION_V2,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_LEGACY,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    AUDIT_START_MISSING_SYSTEM_WORKPLACE,
    AUDIT_START_UNCLASSIFIED_QUESTIONS,
    DEFAULT_AUDIT_PROGRAM_STANDARDS,
    KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED,
    KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_NONE,
    QUESTION_KIND_EDITOR_OPTIONS,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (  # noqa: E402
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_method_v2_backup_service import (  # noqa: E402
    AuditMethodV2BackupError,
    ensure_pre_v2_backup,
    list_pre_v2_backups,
    pre_v2_backup_exists,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service  # noqa: E402
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind  # noqa: E402
from moduly.audity.sluzby.audit_question_snapshot_service import (  # noqa: E402
    AuditV2SnapshotError,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.system_audit_workplace_service import (  # noqa: E402
    SystemAuditWorkplaceError,
    system_audit_workplace_service,
)
from moduly.audity.ui.audity_knowledge_assertion_dialog import (  # noqa: E402
    AudityKnowledgeAssertionDialog,
)
from moduly.audity.ui.audity_knowledge_editor_dialog import (  # noqa: E402
    AudityKnowledgeEditorDialog,
)
from moduly.nastaveni.sluzby.settings_service import settings_service  # noqa: E402

_WS = storage_module.storage_service.base


def _section(section_id: str, name: str, questions: list[dict]) -> dict:
    return {
        "id": section_id,
        "nazev": name,
        "auditni_tvrzeni": questions,
        "sekce": [],
    }


def _fake_tree(process_id: str, process_name: str, section: dict) -> list[KnowledgeTreeNode]:
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id=process_id,
        process_label=process_name,
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id=process_id,
            label=process_name,
            process_id=process_id,
            process_label=process_name,
            section=None,
            children=(section_node,),
        )
    ]


def _q(qid: str, text: str, *, kind: str | None = None, aktivni: bool = True) -> dict:
    item = {
        "id": qid,
        "text": text,
        "aktivni": aktivni,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
    }
    if kind is not None:
        item["question_kind"] = kind
    return item


def _stub_pre_v2_backup():
    """Rychlá náhrada skutečné mbbackup (pro unit testy)."""

    def fake_ensure(**_kwargs):
        if pre_v2_backup_exists():
            return None
        target = (
            storage_module.storage_service.backups_dir
            / "pre_audit_method_v2_stub.mbbackup"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MBBACKUP-STUB")
        return target

    return patch(
        "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
        side_effect=fake_ensure,
    )


class QuestionKindEditorUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_missing_kind_loads_as_unclassified(self) -> None:
        dialog = AudityKnowledgeAssertionDialog(assertion=_q("a1", "Text"))
        self.assertEqual(dialog._current_question_kind(), AUDIT_QUESTION_KIND_UNCLASSIFIED)

    def test_editor_options_exclude_legacy_and_extraordinary(self) -> None:
        values = {value for value, _label in QUESTION_KIND_EDITOR_OPTIONS}
        self.assertNotIn(AUDIT_QUESTION_KIND_LEGACY, values)
        self.assertNotIn(AUDIT_QUESTION_KIND_EXTRAORDINARY, values)
        dialog = AudityKnowledgeAssertionDialog()
        combo_values = {
            dialog._kind_combo.itemData(i) for i in range(dialog._kind_combo.count())
        }
        self.assertEqual(
            combo_values,
            {
                AUDIT_QUESTION_KIND_UNCLASSIFIED,
                AUDIT_QUESTION_KIND_SYSTEM,
                AUDIT_QUESTION_KIND_OPERATION,
            },
        )

    def test_new_assertion_rejects_unclassified(self) -> None:
        dialog = AudityKnowledgeAssertionDialog()
        dialog._text_edit.setPlainText("Nové tvrzení")
        dialog._set_question_kind(AUDIT_QUESTION_KIND_UNCLASSIFIED)
        with patch(
            "moduly.audity.ui.audity_knowledge_assertion_dialog.QMessageBox.warning",
            return_value=0,
        ):
            dialog._accept_if_valid()
        self.assertNotEqual(
            dialog.result(),
            AudityKnowledgeAssertionDialog.DialogCode.Accepted,
        )

    def test_payload_system_and_operation(self) -> None:
        dialog = AudityKnowledgeAssertionDialog()
        dialog._text_edit.setPlainText("Systémové tvrzení")
        dialog._set_question_kind(AUDIT_QUESTION_KIND_SYSTEM)
        self.assertEqual(
            dialog.assertion_payload()["question_kind"], AUDIT_QUESTION_KIND_SYSTEM
        )
        dialog._set_question_kind(AUDIT_QUESTION_KIND_OPERATION)
        self.assertEqual(
            dialog.assertion_payload()["question_kind"], AUDIT_QUESTION_KIND_OPERATION
        )


class SaveAssertionKindTestCase(unittest.TestCase):
    def setUp(self) -> None:
        audit_knowledge_service.ensure_catalogs()
        processes = audit_knowledge_service.get_processes()
        self.assertTrue(processes)
        self.process_id = processes[0].id
        tree = audit_knowledge_service.get_knowledge_tree(ensure=False)
        section_id = None
        for root in tree:
            if root.process_id != self.process_id:
                continue
            for child in root.children:
                if isinstance(child.section, dict):
                    section_id = str(child.section.get("id") or "")
                    break
            if section_id:
                break
        self.assertTrue(section_id)
        self.section_id = section_id
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()

    def tearDown(self) -> None:
        self._backup_patcher.stop()

    def test_save_system_and_operation(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            self.process_id,
            self.section_id,
            {
                "text": "V2b systémová otázka",
                "popis": "",
                "question_kind": AUDIT_QUESTION_KIND_SYSTEM,
                "zavaznost": "stredni",
                "verification_type": "dokumentace",
                "poradi": 9001,
                "aktivni": True,
            },
        )
        self.assertEqual(errors, [])
        errors = audit_knowledge_editor_service.save_assertion(
            self.process_id,
            self.section_id,
            {
                "text": "V2b provozní otázka",
                "popis": "",
                "question_kind": AUDIT_QUESTION_KIND_OPERATION,
                "zavaznost": "stredni",
                "verification_type": "dokumentace",
                "poradi": 9002,
                "aktivni": True,
            },
        )
        self.assertEqual(errors, [])

    def test_reject_unclassified_when_kind_in_payload(self) -> None:
        errors = audit_knowledge_editor_service.save_assertion(
            self.process_id,
            self.section_id,
            {
                "text": "Bez druhu",
                "popis": "",
                "question_kind": AUDIT_QUESTION_KIND_UNCLASSIFIED,
                "zavaznost": "stredni",
                "verification_type": "dokumentace",
                "poradi": 9003,
                "aktivni": True,
            },
        )
        self.assertEqual(errors, [KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED])

    def test_open_editor_does_not_rewrite_json(self) -> None:
        processes = audit_knowledge_service.get_processes()
        process = next(p for p in processes if p.id == self.process_id)
        relative = str(process.soubor_znalosti or "").strip()
        self.assertTrue(relative)
        path = storage_module.storage_service.ciselniky_dir / "audity" / relative
        self.assertTrue(path.is_file())
        before = path.read_text(encoding="utf-8")
        AudityKnowledgeEditorDialog()
        after = path.read_text(encoding="utf-8")
        self.assertEqual(before, after)


class UnclassifiedCountTestCase(unittest.TestCase):
    def test_counts_only_active_unclassified(self) -> None:
        section = _section(
            "s1",
            "Sekce",
            [
                _q("a", "A"),  # unclassified active
                _q("b", "B", kind=AUDIT_QUESTION_KIND_OPERATION),
                _q("c", "C", aktivni=False),  # inactive unclassified
                _q("d", "D", kind=AUDIT_QUESTION_KIND_SYSTEM),
            ],
        )
        tree = _fake_tree("p1", "Proces", section)
        count = audit_knowledge_service.count_unclassified_active_assertions(
            ensure=False,
            knowledge_tree=tree,
        )
        self.assertEqual(count, 1)


class SystemWorkplaceUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        system_audit_workplace_service.settings_path().unlink(missing_ok=True)
        self.wp = settings_service.save_workplace(name="V2b systém UI", active=True)

    def test_load_and_discard_system_workplace(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        self.assertEqual(dialog._system_workplace_combo.currentData(), None)
        self.assertIn(
            KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_NONE,
            dialog._system_workplace_combo.itemText(0),
        )

        index = dialog._system_workplace_combo.findData(self.wp.id)
        self.assertGreaterEqual(index, 0)
        dialog._system_workplace_combo.setCurrentIndex(index)
        self.assertTrue(dialog._system_workplace_dirty)
        self.assertTrue(dialog._has_unsaved_changes())

        dialog._discard_all_drafts()
        self.assertIsNone(system_audit_workplace_service.get_system_audit_workplace_id())
        self.assertFalse(dialog._system_workplace_dirty)

    def test_apply_saves_system_workplace(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        index = dialog._system_workplace_combo.findData(self.wp.id)
        dialog._system_workplace_combo.setCurrentIndex(index)
        with _stub_pre_v2_backup():
            self.assertTrue(dialog._save_system_workplace_if_needed())
        self.assertEqual(
            system_audit_workplace_service.get_system_audit_workplace_id(),
            self.wp.id,
        )


class PreV2BackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        system_audit_workplace_service.settings_path().unlink(missing_ok=True)
        for backup in list_pre_v2_backups():
            backup.unlink(missing_ok=True)

    def test_backup_once_before_system_workplace_save(self) -> None:
        wp = settings_service.save_workplace(name="V2b backup wp", active=True)
        self.assertFalse(pre_v2_backup_exists())
        created: list[Path] = []

        def fake_create(*, target_path, **_kwargs):
            path = Path(target_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"MBBACKUP-FAKE")
            created.append(path)
            return path

        with patch(
            "moduly.audity.sluzby.audit_method_v2_backup_service.create_verified_pre_migration_backup",
            side_effect=fake_create,
        ):
            system_audit_workplace_service.set_system_audit_workplace_id(wp.id)
            self.assertEqual(len(created), 1)
            self.assertTrue(pre_v2_backup_exists())
            system_audit_workplace_service.set_system_audit_workplace_id(None)
            self.assertEqual(len(created), 1)

    def test_backup_failure_blocks_save(self) -> None:
        wp = settings_service.save_workplace(name="V2b backup fail", active=True)
        with patch(
            "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
            side_effect=AuditMethodV2BackupError("záloha selhala"),
        ):
            with self.assertRaises(AuditMethodV2BackupError):
                system_audit_workplace_service.set_system_audit_workplace_id(wp.id)
        self.assertIsNone(system_audit_workplace_service.get_system_audit_workplace_id())


class StartAuditMessagesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        system_audit_workplace_service.settings_path().unlink(missing_ok=True)
        self.system_wp = settings_service.save_workplace(name="V2b start sys", active=True)
        self.ops_wp = settings_service.save_workplace(name="V2b start ops", active=True)
        self.program = audit_program_service.create_program(
            name="V2b start",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            self.program.id,
            workplace_id=self.ops_wp.id,
            workplace_name=self.ops_wp.name,
            audit_interval_months=6,
        )
        self.visit = audit_program_service.add_visit(
            self.program.id,
            workplace_id=self.ops_wp.id,
            planned_year=2026,
            planned_month=7,
        )
        audit_program_service.add_visit_process(
            self.visit.id,
            process_id="proc_v2b",
            process_name="Proces V2b",
        )

    def _set_system(self) -> None:
        with _stub_pre_v2_backup():
            system_audit_workplace_service.set_system_audit_workplace_id(self.system_wp.id)

    def test_missing_system_workplace_message(self) -> None:
        audit = audit_program_service.create_audit_from_visit(self.visit.id, started_at=date(2026, 4, 10))
        with self.assertRaises(SystemAuditWorkplaceError) as ctx:
            audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertEqual(str(ctx.exception), AUDIT_START_MISSING_SYSTEM_WORKPLACE)

    def test_unclassified_blocks_with_overview(self) -> None:
        self._set_system()
        tree = _fake_tree(
            "proc_v2b",
            "Proces V2b",
            _section(
                "sec_v2b",
                "Sekce V2b",
                [_q("unc_q", "Nezařazená otázka text")],
            ),
        )
        before = len(audit_service.get_all())
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=tree
        ):
            audit = audit_program_service.create_audit_from_visit(
                self.visit.id, started_at=date(2026, 4, 10)
            )
            with self.assertRaises(AuditV2SnapshotError) as ctx:
                audit_program_service.prepare_audit_from_visit(audit.id)
        message = str(ctx.exception)
        self.assertIn(AUDIT_START_UNCLASSIFIED_QUESTIONS, message)
        self.assertIn("Proces V2b", message)
        self.assertIn("Sekce V2b", message)
        self.assertIn("unc_q", message)
        self.assertEqual(len(audit_service.get_all()), before + 1)
        visit = audit_program_service.repository.get_visit(self.visit.id)
        assert visit is not None
        self.assertEqual(visit.audit_id, audit.id)

    def test_classified_creates_v2_snapshot(self) -> None:
        self._set_system()
        tree = _fake_tree(
            "proc_v2b",
            "Proces V2b",
            _section(
                "sec_v2b",
                "Sekce V2b",
                [
                    _q("sys_q", "Systém", kind=AUDIT_QUESTION_KIND_SYSTEM),
                    _q("ops_q", "Provoz", kind=AUDIT_QUESTION_KIND_OPERATION),
                ],
            ),
        )
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=tree
        ):
            audit = audit_program_service.create_audit_from_visit(self.visit.id, started_at=date(2026, 4, 10))
            audit = audit_program_service.prepare_audit_from_visit(audit.id)
        self.assertEqual(audit.methodology_generation, AUDIT_METHODOLOGY_GENERATION_V2)
        self.assertEqual(audit.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"ops_q"})
        self.assertTrue(all(s.is_in_scope for s in snaps))

    def test_system_visit_gets_system_only(self) -> None:
        self._set_system()
        audit_program_service.add_workplace(
            self.program.id,
            workplace_id=self.system_wp.id,
            workplace_name=self.system_wp.name,
            audit_interval_months=6,
        )
        visit = audit_program_service.add_visit(
            self.program.id,
            workplace_id=self.system_wp.id,
            planned_year=2026,
            planned_month=8,
        )
        audit_program_service.add_visit_process(
            visit.id,
            process_id="proc_v2b",
            process_name="Proces V2b",
        )
        tree = _fake_tree(
            "proc_v2b",
            "Proces V2b",
            _section(
                "sec_v2b",
                "Sekce V2b",
                [
                    _q("sys_q", "Systém", kind=AUDIT_QUESTION_KIND_SYSTEM),
                    _q("ops_q", "Provoz", kind=AUDIT_QUESTION_KIND_OPERATION),
                ],
            ),
        )
        with patch.object(
            audit_knowledge_service, "get_knowledge_tree", return_value=tree
        ):
            audit = audit_program_service.create_audit_from_visit(visit.id, started_at=date(2026, 4, 10))
            audit = audit_program_service.prepare_audit_from_visit(audit.id)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual({s.assertion_id for s in snaps}, {"sys_q"})

    def test_legacy_audit_unchanged_after_json_edit(self) -> None:
        legacy = audit_service.create_audit(
            workplace_id=self.ops_wp.id,
            workplace_name=self.ops_wp.name,
            year=2025,
            planned_month=1,
        )
        with get_session() as session:
            db = session.get(Audit, legacy.id)
            assert db is not None
            db.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            db.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
            session.add(
                AuditQuestionSnapshot(
                    audit_id=legacy.id,
                    process_id="p",
                    process_name="P",
                    section_id="s",
                    section_name="S",
                    assertion_id="legacy_keep",
                    assertion_text="Původní text",
                    verification_type="dokumentace",
                    severity="stredni",
                    question_kind=AUDIT_QUESTION_KIND_LEGACY,
                    display_order=1,
                    is_in_scope=True,
                )
            )
            session.commit()

        reloaded = audit_service.get_by_id(legacy.id)
        assert reloaded is not None
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == legacy.id
                    )
                )
            )
        self.assertEqual(snaps[0].assertion_text, "Původní text")
        self.assertEqual(snaps[0].question_kind, AUDIT_QUESTION_KIND_LEGACY)


class CancelAssertionDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_cancel_assertion_dialog_does_not_save_kind(self) -> None:
        dialog = AudityKnowledgeAssertionDialog(assertion=_q("x", "Původní"))
        dialog._set_question_kind(AUDIT_QUESTION_KIND_SYSTEM)
        dialog.reject()
        self.assertNotEqual(
            dialog.result(),
            AudityKnowledgeAssertionDialog.DialogCode.Accepted,
        )


if __name__ == "__main__":
    unittest.main()
