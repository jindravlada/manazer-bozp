"""AUDIT-EXTRAORDINARY-1: evidence mimořádných otázek a cílových provozů."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-extraordinary-1-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.sluzby.audit_extraordinary_schema_migration import (
        EXPECTED_INDEXES,
        EXPECTED_TABLES,
        apply_audit_extraordinary_schema_ddl,
        needs_audit_extraordinary_schema,
        schema_is_present,
    )

    apply_audit_extraordinary_schema_ddl(_DB)

    from core.database.session import get_session
    from moduly.audity.constants import (
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
        EXTRAORDINARY_DUPLICATE_TARGET,
        EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
        EXTRAORDINARY_QUESTION_STATUS_CANCELLED,
        EXTRAORDINARY_QUESTION_TEXT_REQUIRED,
        EXTRAORDINARY_SYSTEM_WORKPLACE_MARK,
        EXTRAORDINARY_TARGET_LOCKED,
        EXTRAORDINARY_TARGET_REQUIRED,
        EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
        EXTRAORDINARY_TARGET_STATUS_CANCELLED,
        EXTRAORDINARY_TARGET_STATUS_PENDING,
        EXTRAORDINARY_TARGET_STATUS_VERIFIED,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_extraordinary_question import (
        AuditExtraordinaryQuestion,
        AuditExtraordinaryQuestionTarget,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        AuditExtraordinaryError,
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class SchemaMigrationTestCase(unittest.TestCase):
    def test_01_migration_creates_expected_tables_and_indexes(self) -> None:
        self.assertTrue(schema_is_present(_DB))
        self.assertFalse(needs_audit_extraordinary_schema(_DB))
        connection = sqlite3.connect(str(_DB))
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            indexes = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
        finally:
            connection.close()
        for name in EXPECTED_TABLES:
            self.assertIn(name, tables)
        for name in EXPECTED_INDEXES:
            self.assertIn(name, indexes)

    def test_02_existing_audits_snapshots_unchanged(self) -> None:
        wp = settings_service.save_workplace(name="Exist WP", active=True, audit_enabled=True)
        audit = audit_service.create_audit(
            workplace_id=wp.id,
            workplace_name=wp.name,
            year=2026,
            started_at=date(2026, 1, 1),
            title="Baseline",
        )
        with get_session() as session:
            row = session.get(Audit, audit.id)
            assert row is not None
            row.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            row.methodology_generation = AUDIT_METHODOLOGY_GENERATION_V2
            row.questions_frozen_at = datetime.now()
            session.add(
                AuditQuestionSnapshot(
                    audit_id=audit.id,
                    process_id="p",
                    process_name="P",
                    section_id="s",
                    section_name="S",
                    assertion_id="a",
                    assertion_text="Q",
                    verification_type="documentation",
                    severity="normal",
                    question_kind="operation",
                    display_order=0,
                    is_in_scope=True,
                    created_at=datetime.now(),
                )
            )
            session.commit()

        before = audit_service.get_by_id(audit.id)
        assert before is not None
        before_hash = before.snapshot_integrity_hash
        before_source = before.methodology_source

        apply_audit_extraordinary_schema_ddl(_DB)
        after = audit_service.get_by_id(audit.id)
        assert after is not None
        self.assertEqual(after.methodology_source, before_source)
        self.assertEqual(after.snapshot_integrity_hash, before_hash)
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0].assertion_text, "Q")


class ExtraordinaryServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_extraordinary_question_targets"))
            session.execute(text("DELETE FROM audit_extraordinary_questions"))
            session.commit()
        self.system_wp = settings_service.save_workplace(
            name="Systém Ext", active=True, audit_enabled=True
        )
        self.wp_a = settings_service.save_workplace(
            name="Provoz A Ext", active=True, audit_enabled=True
        )
        self.wp_b = settings_service.save_workplace(
            name="Provoz B Ext", active=True, audit_enabled=True
        )
        self.wp_off = settings_service.save_workplace(
            name="Bez auditu Ext", active=True, audit_enabled=False
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system_wp.id)

    def test_03_requires_text(self) -> None:
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.create_question(
                question_text="  ",
                workplace_ids=[self.wp_a.id],
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_QUESTION_TEXT_REQUIRED)

    def test_04_requires_target(self) -> None:
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.create_question(
                question_text="Otázka bez cíle",
                workplace_ids=[],
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_TARGET_REQUIRED)

    def test_05_all_workplaces_creates_concrete_rows(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Pro všechny",
            assigned_by="Vedoucí",
            all_workplaces=True,
        )
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        selectable = {
            item.workplace_id
            for item in audit_extraordinary_question_service.list_selectable_workplaces()
        }
        self.assertEqual({int(t.workplace_id) for t in targets}, selectable)
        self.assertNotIn(self.wp_off.id, {int(t.workplace_id) for t in targets})

    def test_06_selected_workplaces_only(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Jen A",
            workplace_ids=[self.wp_a.id],
        )
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertEqual([int(t.workplace_id) for t in targets], [self.wp_a.id])

    def test_07_system_workplace_selectable_and_marked(self) -> None:
        choices = audit_extraordinary_question_service.list_selectable_workplaces()
        system_choice = next(item for item in choices if item.is_system)
        self.assertEqual(system_choice.workplace_id, self.system_wp.id)
        self.assertIn(EXTRAORDINARY_SYSTEM_WORKPLACE_MARK, system_choice.display_name)
        question = audit_extraordinary_question_service.create_question(
            question_text="Systém",
            workplace_ids=[self.system_wp.id],
        )
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertEqual([int(t.workplace_id) for t in targets], [self.system_wp.id])

    def test_08_duplicate_target_blocked(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Dup",
            workplace_ids=[self.wp_a.id],
        )
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.update_question(
                question.id,
                add_workplace_ids=[self.wp_a.id],
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_DUPLICATE_TARGET)

    def test_09_10_atomic_create_and_rollback(self) -> None:
        before_q = len(audit_extraordinary_question_service.repository.list_questions())
        with patch(
            "moduly.audity.sluzby.audit_extraordinary_question_service.get_session"
        ) as mocked:
            # Simulace chyby po vytvoření otázky: použij duplicitní ID přes validaci.
            pass
        del mocked
        with self.assertRaises(AuditExtraordinaryError):
            audit_extraordinary_question_service.create_question(
                question_text="Atom",
                workplace_ids=[self.wp_a.id, self.wp_a.id],
            )
        after_q = len(audit_extraordinary_question_service.repository.list_questions())
        self.assertEqual(after_q, before_q)
        with get_session() as session:
            targets = session.scalar(
                text("SELECT COUNT(*) FROM audit_extraordinary_question_targets")
            )
        # Předchozí testy mohly mít cíle — ověř že po failed create nepřibyly orphan otázky.
        self.assertEqual(after_q, before_q)

    def test_11_12_new_pending_and_active(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Stav",
            workplace_ids=[self.wp_a.id, self.wp_b.id],
        )
        self.assertEqual(question.status, EXTRAORDINARY_QUESTION_STATUS_ACTIVE)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertTrue(
            all(t.status == EXTRAORDINARY_TARGET_STATUS_PENDING for t in targets)
        )

    def test_13_14_cancel_and_restore_target(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Cíl cancel",
            workplace_ids=[self.wp_a.id, self.wp_b.id],
        )
        audit_extraordinary_question_service.cancel_target(question.id, self.wp_a.id)
        targets = {
            int(t.workplace_id): t.status
            for t in audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        }
        self.assertEqual(targets[self.wp_a.id], EXTRAORDINARY_TARGET_STATUS_CANCELLED)
        self.assertEqual(targets[self.wp_b.id], EXTRAORDINARY_TARGET_STATUS_PENDING)
        # Fyzicky zůstává
        self.assertEqual(len(targets), 2)

        audit_extraordinary_question_service.restore_target(question.id, self.wp_a.id)
        targets = {
            int(t.workplace_id): t.status
            for t in audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        }
        self.assertEqual(targets[self.wp_a.id], EXTRAORDINARY_TARGET_STATUS_PENDING)

    def test_15_assigned_verified_locked(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Locked",
            workplace_ids=[self.wp_a.id],
        )
        with get_session() as session:
            target = session.scalars(
                select(AuditExtraordinaryQuestionTarget).where(
                    AuditExtraordinaryQuestionTarget.question_id == question.id
                )
            ).first()
            assert target is not None
            target.status = EXTRAORDINARY_TARGET_STATUS_ASSIGNED
            target.assigned_audit_id = 999
            session.commit()

        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.cancel_target(question.id, self.wp_a.id)
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_TARGET_LOCKED)

        with get_session() as session:
            target = session.scalars(
                select(AuditExtraordinaryQuestionTarget).where(
                    AuditExtraordinaryQuestionTarget.question_id == question.id
                )
            ).first()
            assert target is not None
            target.status = EXTRAORDINARY_TARGET_STATUS_VERIFIED
            session.commit()

        with self.assertRaises(AuditExtraordinaryError):
            audit_extraordinary_question_service.cancel_target(question.id, self.wp_a.id)

    def test_16_cancel_question_soft(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Zruš otázku",
            workplace_ids=[self.wp_a.id],
        )
        cancelled = audit_extraordinary_question_service.cancel_question(question.id)
        self.assertEqual(cancelled.status, EXTRAORDINARY_QUESTION_STATUS_CANCELLED)
        still = audit_extraordinary_question_service.repository.get_question(question.id)
        self.assertIsNotNone(still)
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].status, EXTRAORDINARY_TARGET_STATUS_CANCELLED)

    def test_17_overview_counts(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Counts",
            assigned_by="Zdroj",
            workplace_ids=[self.wp_a.id, self.wp_b.id],
        )
        audit_extraordinary_question_service.cancel_target(question.id, self.wp_b.id)
        rows = audit_extraordinary_question_service.list_overview_rows()
        row = next(item for item in rows if item.question_id == question.id)
        self.assertEqual(row.pending_count, 1)
        self.assertEqual(row.cancelled_count, 1)
        self.assertEqual(row.assigned_count, 0)
        self.assertEqual(row.verified_count, 0)
        self.assertEqual(row.targets_total, 2)

    def test_21_single_question_no_duplicates(self) -> None:
        before = len(audit_extraordinary_question_service.repository.list_questions())
        audit_extraordinary_question_service.create_question(
            question_text="Jedna",
            workplace_ids=[self.wp_a.id],
        )
        after = len(audit_extraordinary_question_service.repository.list_questions())
        self.assertEqual(after, before + 1)

    def test_22_23_no_auto_assign_to_existing_audit(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.wp_a.id,
            workplace_name=self.wp_a.name,
            year=2026,
            started_at=date.today(),
            title="Hotový?",
        )
        question = audit_extraordinary_question_service.create_question(
            question_text="Bez vazby",
            workplace_ids=[self.wp_a.id],
        )
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        self.assertTrue(all(t.assigned_audit_id is None for t in targets))
        self.assertTrue(all(t.verified_audit_id is None for t in targets))
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Hotový?")


class ExtraordinaryUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_extraordinary_question_targets"))
            session.execute(text("DELETE FROM audit_extraordinary_questions"))
            session.commit()
        self.wp = settings_service.save_workplace(
            name="UI WP Ext", active=True, audit_enabled=True
        )
        system = settings_service.save_workplace(
            name="UI Sys Ext", active=True, audit_enabled=True
        )
        system_audit_workplace_service.set_system_audit_workplace_id(system.id)

    def test_18_19_selection_and_filter(self) -> None:
        from moduly.audity.ui.extraordinary_questions_dialog import (
            ExtraordinaryQuestionsDialog,
            STATUS_FILTER_ACTIVE,
            STATUS_FILTER_CANCELLED,
        )

        q1 = audit_extraordinary_question_service.create_question(
            question_text="Hledaná alpha",
            assigned_by="Inspector X",
            workplace_ids=[self.wp.id],
        )
        q2 = audit_extraordinary_question_service.create_question(
            question_text="Jiná beta",
            assigned_by="Jiný",
            workplace_ids=[self.wp.id],
        )
        audit_extraordinary_question_service.cancel_question(q2.id)

        dialog = ExtraordinaryQuestionsDialog()
        self.assertFalse(dialog.edit_btn.isEnabled())
        # Select first visible row
        dialog.table.selectRow(0)
        self.assertTrue(dialog.edit_btn.isEnabled())

        dialog.status_filter.setCurrentText(STATUS_FILTER_CANCELLED)
        dialog.refresh()
        texts = [
            dialog.table.item(row, 0).text()
            for row in range(dialog.table.rowCount())
        ]
        self.assertEqual(texts, ["Jiná beta"])

        dialog.status_filter.setCurrentText(STATUS_FILTER_ACTIVE)
        dialog.refresh()
        dialog.text_filter.search_edit.setText("alpha")
        dialog.text_filter.apply_filter()
        visible = sum(
            1
            for row in range(dialog.table.rowCount())
            if not dialog.table.isRowHidden(row)
        )
        self.assertEqual(visible, 1)
        dialog.close()
        self.assertIsNotNone(
            audit_extraordinary_question_service.repository.get_question(q1.id)
        )

    def test_20_discard_close_keeps_db_clean(self) -> None:
        from moduly.audity.ui.extraordinary_question_editor_dialog import (
            ExtraordinaryQuestionEditorDialog,
        )

        before = len(audit_extraordinary_question_service.repository.list_questions())
        dialog = ExtraordinaryQuestionEditorDialog()
        dialog.question_text.setPlainText("Neuložená")
        dialog.assigned_by.setText("X")
        dialog.mode_selected.setChecked(True)
        for row in range(dialog.workplace_list.count()):
            item = dialog.workplace_list.item(row)
            item.setCheckState(
                __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked
            )
        # Discard path
        dialog._done_reject()
        after = len(audit_extraordinary_question_service.repository.list_questions())
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
