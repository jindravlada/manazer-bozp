"""AUDIT-METHOD-V2b-UX1: přímá změna druhu otázky v tabulce tvrzení."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-method-v2b-ux1-"))
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

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402
from sqlalchemy import select  # noqa: E402

from core.database.session import get_session  # noqa: E402
from core.services.editable_catalog_service import editable_catalog_service  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    AUDIT_QUESTION_KIND_LEGACY,
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    QUESTION_KIND_EDITOR_OPTIONS,
)
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (  # noqa: E402
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service  # noqa: E402
from moduly.audity.sluzby.audit_method_v2_backup_service import (  # noqa: E402
    list_pre_v2_backups,
    pre_v2_backup_exists,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind  # noqa: E402
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.ui.audity_knowledge_assertion_dialog import (  # noqa: E402
    AudityKnowledgeAssertionDialog,
)
from moduly.audity.ui.audity_knowledge_assertions_widget import (  # noqa: E402
    AudityKnowledgeAssertionsWidget,
)
from moduly.audity.ui.audity_knowledge_editor_dialog import (  # noqa: E402
    AudityKnowledgeEditorDialog,
)

_PROCESS_ID = "urazy_mimo_udalosti"
_SECTION_ID = "evidence_hlaseni_urazu"
_ASSERTION_ID = "vsechny_urazy_evidovany"
_COL_KIND = 2


def _stub_pre_v2_backup():
    def fake_ensure(**_kwargs):
        if pre_v2_backup_exists():
            return None
        # Stejný storage binding jako list_pre_v2_backups (odolné vůči reload Path.home).
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            allocate_pre_v2_backup_path,
        )

        target = allocate_pre_v2_backup_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"MBBACKUP-STUB")
        return target

    return patch(
        "moduly.audity.sluzby.audit_method_v2_backup_service.ensure_pre_v2_backup",
        side_effect=fake_ensure,
    )


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


def _section(section_id: str, name: str, questions: list[dict]) -> dict:
    return {
        "id": section_id,
        "nazev": name,
        "auditni_tvrzeni": questions,
        "sekce": [],
    }


class KindComboTableTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _load_widget(self) -> AudityKnowledgeAssertionsWidget:
        widget = AudityKnowledgeAssertionsWidget()
        section = _section(
            "s1",
            "Sekce",
            [
                _q("a1", "Nezařazená A"),
                _q("a2", "Systémová", kind=AUDIT_QUESTION_KIND_SYSTEM),
                _q("a3", "Provozní", kind=AUDIT_QUESTION_KIND_OPERATION),
            ],
        )
        widget.load_section(process_id="p1", section_id="s1", section=section)
        return widget

    def _kind_combo(self, widget: AudityKnowledgeAssertionsWidget, row: int) -> QComboBox:
        combo = widget._table.cellWidget(row, _COL_KIND)
        self.assertIsInstance(combo, QComboBox)
        assert isinstance(combo, QComboBox)
        return combo

    def _set_kind(self, combo: QComboBox, kind: str) -> None:
        index = combo.findData(kind)
        self.assertGreaterEqual(index, 0)
        combo.setCurrentIndex(index)

    def test_column_has_combo_with_editor_options_only(self) -> None:
        widget = self._load_widget()
        combo = self._kind_combo(widget, 0)
        values = {combo.itemData(i) for i in range(combo.count())}
        self.assertEqual(
            values,
            {
                AUDIT_QUESTION_KIND_UNCLASSIFIED,
                AUDIT_QUESTION_KIND_SYSTEM,
                AUDIT_QUESTION_KIND_OPERATION,
            },
        )
        self.assertNotIn(AUDIT_QUESTION_KIND_LEGACY, values)
        self.assertNotIn(AUDIT_QUESTION_KIND_EXTRAORDINARY, values)
        option_values = {value for value, _label in QUESTION_KIND_EDITOR_OPTIONS}
        self.assertEqual(values, option_values)

    def test_loads_working_copy_values(self) -> None:
        widget = self._load_widget()
        self.assertEqual(self._kind_combo(widget, 0).currentData(), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        self.assertEqual(self._kind_combo(widget, 1).currentData(), AUDIT_QUESTION_KIND_SYSTEM)
        self.assertEqual(self._kind_combo(widget, 2).currentData(), AUDIT_QUESTION_KIND_OPERATION)

    def test_kind_change_updates_unclassified_count_and_pending(self) -> None:
        widget = self._load_widget()
        self.assertEqual(widget.count_unclassified_active_in_section(), 1)

        self._set_kind(self._kind_combo(widget, 0), AUDIT_QUESTION_KIND_SYSTEM)
        self.assertEqual(widget.count_unclassified_active_in_section(), 0)
        self.assertTrue(widget.has_pending_question_kinds())

        self._set_kind(self._kind_combo(widget, 0), AUDIT_QUESTION_KIND_OPERATION)
        self.assertEqual(widget.count_unclassified_active_in_section(), 0)

        self._set_kind(self._kind_combo(widget, 1), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        self.assertEqual(widget.count_unclassified_active_in_section(), 1)

    def test_rebuild_preserves_pending_kind(self) -> None:
        widget = self._load_widget()
        self._set_kind(self._kind_combo(widget, 0), AUDIT_QUESTION_KIND_SYSTEM)
        # Přestavba ze „diskové“ sekce (bez question_kind) musí zachovat pending.
        disk_section = _section("s1", "Sekce", [_q("a1", "Nezařazená A"), _q("a2", "Systémová", kind=AUDIT_QUESTION_KIND_SYSTEM), _q("a3", "Provozní", kind=AUDIT_QUESTION_KIND_OPERATION)])
        widget.load_section(process_id="p1", section_id="s1", section=disk_section)
        self.assertEqual(self._kind_combo(widget, 0).currentData(), AUDIT_QUESTION_KIND_SYSTEM)
        self.assertTrue(widget.has_pending_question_kinds())

    def test_detail_reads_table_pending_kind(self) -> None:
        widget = self._load_widget()
        self._set_kind(self._kind_combo(widget, 0), AUDIT_QUESTION_KIND_SYSTEM)
        widget._table.selectRow(0)
        selected = widget._selected_assertion()
        assert selected is not None
        detail = AudityKnowledgeAssertionDialog(assertion=selected)
        self.assertEqual(detail._current_question_kind(), AUDIT_QUESTION_KIND_SYSTEM)


class KindComboPersistTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        audit_knowledge_editor_service.ensure_user_catalogs()
        self._path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        bundled = editable_catalog_service.bundled_path("audity/urazy_mimo_udalosti.json")
        shutil.copy2(bundled, self._path)
        audit_knowledge_service.ensure_catalogs()
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)
        self._backup_patcher = _stub_pre_v2_backup()
        self._backup_patcher.start()

    def tearDown(self) -> None:
        self._backup_patcher.stop()
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _json_fingerprint(self) -> str:
        return self._path.read_text(encoding="utf-8")

    def _assertion_kind_on_disk(self) -> str:
        with self._path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        for section in payload.get("sekce") or []:
            if section.get("id") != _SECTION_ID:
                continue
            for item in section.get("auditni_tvrzeni") or []:
                if item.get("id") == _ASSERTION_ID:
                    return interpret_question_kind(item.get("question_kind"))
        self.fail("assertion not found")

    def _open_section_dialog(self) -> AudityKnowledgeEditorDialog:
        dialog = AudityKnowledgeEditorDialog()
        first_process = dialog.knowledge_tree.topLevelItem(0)
        self.assertIsNotNone(first_process)
        # Najdi proces úrazů.
        process_item = None
        for i in range(dialog.knowledge_tree.topLevelItemCount()):
            item = dialog.knowledge_tree.topLevelItem(i)
            if item is not None and _PROCESS_ID in str(item.data(0, Qt.ItemDataRole.UserRole) or ""):
                process_item = item
                break
            # fallback: match by text / select by API
        if process_item is None:
            self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID))
        else:
            section_item = None
            for i in range(process_item.childCount()):
                child = process_item.child(i)
                payload = child.data(0, Qt.ItemDataRole.UserRole)
                if _SECTION_ID in str(payload or ""):
                    section_item = child
                    break
            if section_item is not None:
                dialog.knowledge_tree.setCurrentItem(section_item)
            else:
                self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID))
        self.assertTrue(dialog.section_editor.has_section())
        return dialog

    def _kind_combo_for_assertion(
        self, dialog: AudityKnowledgeEditorDialog, assertion_id: str
    ) -> QComboBox:
        widget = dialog.section_editor._assertions_widget
        for row in range(widget._table.rowCount()):
            combo = widget._table.cellWidget(row, _COL_KIND)
            if isinstance(combo, QComboBox) and combo.property("assertion_id") == assertion_id:
                return combo
        self.fail(f"combo for {assertion_id} not found")

    def test_change_marks_dirty_without_json_write(self) -> None:
        dialog = self._open_section_dialog()
        before = self._json_fingerprint()
        before_count = int(
            dialog._unclassified_count_label.text().rsplit(":", 1)[-1].strip()
        )
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        self.assertEqual(combo.currentData(), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        index = combo.findData(AUDIT_QUESTION_KIND_SYSTEM)
        combo.setCurrentIndex(index)
        self.assertTrue(dialog._has_unsaved_changes())
        self.assertEqual(self._json_fingerprint(), before)
        after_count = int(
            dialog._unclassified_count_label.text().rsplit(":", 1)[-1].strip()
        )
        self.assertEqual(after_count, before_count - 1)

    def test_apply_writes_question_kind(self) -> None:
        dialog = self._open_section_dialog()
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_OPERATION))
        self.assertTrue(dialog._flush_pending_assertion_kinds())
        self.assertEqual(self._assertion_kind_on_disk(), AUDIT_QUESTION_KIND_OPERATION)
        self.assertFalse(dialog.section_editor.has_pending_assertion_kinds())

    def test_discard_and_escape_revert_kind(self) -> None:
        dialog = self._open_section_dialog()
        before = self._json_fingerprint()
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        dialog._discard_all_drafts()
        self.assertEqual(self._json_fingerprint(), before)
        self.assertEqual(self._assertion_kind_on_disk(), AUDIT_QUESTION_KIND_UNCLASSIFIED)
        self.assertFalse(dialog._has_unsaved_changes())

        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        with patch(
            "moduly.audity.ui.audity_knowledge_editor_dialog.confirm_close_with_unsaved_changes",
            return_value="discard",
        ):
            dialog.reject()
        self.assertEqual(self._json_fingerprint(), before)

    def test_detail_updates_table_combo(self) -> None:
        dialog = self._open_section_dialog()
        widget = dialog.section_editor._assertions_widget
        for row, item in enumerate(widget._assertions):
            if item.get("id") == _ASSERTION_ID:
                widget._table.selectRow(row)
                break
        selected = widget._selected_assertion()
        assert selected is not None
        detail = AudityKnowledgeAssertionDialog(
            existing_ids=widget._existing_ids(),
            assertion=selected,
            parent=widget,
        )
        detail._set_question_kind(AUDIT_QUESTION_KIND_SYSTEM)
        # Simulace potvrzení detailu (stejná cesta jako Accept).
        errors = audit_knowledge_editor_service.save_assertion(
            _PROCESS_ID,
            _SECTION_ID,
            detail.assertion_payload(),
            assertion_id=_ASSERTION_ID,
        )
        self.assertEqual(errors, [])
        key = widget._pending_key(_ASSERTION_ID)
        widget._pending_kinds.pop(key, None)
        widget._disk_kinds[key] = AUDIT_QUESTION_KIND_SYSTEM
        widget.reload_assertions()
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        self.assertEqual(combo.currentData(), AUDIT_QUESTION_KIND_SYSTEM)

    def test_section_switch_keeps_pending(self) -> None:
        dialog = self._open_section_dialog()
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        self.assertTrue(dialog.section_editor.has_pending_assertion_kinds())
        # Přepni na proces a zpět na stejnou sekci.
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID))
        self.assertTrue(dialog.knowledge_tree.select_node(_PROCESS_ID, _SECTION_ID))
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        self.assertEqual(combo.currentData(), AUDIT_QUESTION_KIND_SYSTEM)
        self.assertTrue(dialog.section_editor.has_pending_assertion_kinds())

    def test_first_flush_creates_one_pre_v2_backup(self) -> None:
        for backup in list_pre_v2_backups():
            backup.unlink(missing_ok=True)
        self.assertFalse(pre_v2_backup_exists())
        dialog = self._open_section_dialog()
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_SYSTEM))
        before_count = len(list_pre_v2_backups())
        self.assertTrue(dialog._flush_pending_assertion_kinds())
        after_first = len(list_pre_v2_backups())
        self.assertEqual(after_first, before_count + 1)
        self.assertTrue(pre_v2_backup_exists())
        combo = self._kind_combo_for_assertion(dialog, _ASSERTION_ID)
        combo.setCurrentIndex(combo.findData(AUDIT_QUESTION_KIND_OPERATION))
        self.assertTrue(dialog._flush_pending_assertion_kinds())
        self.assertEqual(len(list_pre_v2_backups()), after_first)


class LegacySnapshotUnchangedTestCase(unittest.TestCase):
    def test_kind_change_does_not_alter_legacy_snapshot(self) -> None:
        from moduly.audity.modely.audit import Audit

        legacy = audit_service.create_audit(
            workplace_id=None,
            workplace_name="",
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
            audit_id = legacy.id

        with get_session() as session:
            before = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit_id
                    )
                )
            )
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0].assertion_text, "Původní text")

        audit_knowledge_editor_service.ensure_user_catalogs()
        path = audit_knowledge_service.audity_dir / "urazy_mimo_udalosti.json"
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        with get_session() as session:
            after = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit_id
                    )
                )
            )
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].assertion_text, "Původní text")
        self.assertEqual(after[0].question_kind, AUDIT_QUESTION_KIND_LEGACY)


if __name__ == "__main__":
    unittest.main()
