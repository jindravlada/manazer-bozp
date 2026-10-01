"""AUDIT-EXPECTED-END-2: předpokládané datum ukončení vícedenního auditu."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-expected-end-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_AUDIT,
        ITEM_TYPE_INSPECTION,
        ITEM_TYPE_TASK,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.database.upgrade_guard import prepare_database_for_startup
    from moduly.audity.constants import (
        AUDIT_EXPECTED_END_BEFORE_START_MESSAGE,
        AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
    )
    from moduly.audity.sluzby.audit_expected_end_2_schema_migration import (
        apply_audit_expected_end_2_schema_ddl,
        needs_audit_expected_end_2_schema,
        prepare_audit_expected_end_2_schema,
        schema_is_present,
    )
    from moduly.audity.sluzby.audit_service import AuditService, audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_spis_widget import AuditSpisWidget
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service
    from PySide6.QtWidgets import QApplication, QFormLayout, QGroupBox


def _column_meta(db_path: Path, column_name: str) -> tuple | None:
    connection = sqlite3.connect(str(db_path))
    try:
        for row in connection.execute("PRAGMA table_info(audits)").fetchall():
            if str(row[1]) == column_name:
                return row
        return None
    finally:
        connection.close()


class AuditExpectedEnd2BehaviorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def test_01_initializer_column_is_nullable_without_default(self) -> None:
        meta = _column_meta(storage_module.storage_service.database_path, "expected_end_date")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(str(meta[2]).upper(), "DATE")
        self.assertEqual(int(meta[3]), 0)
        self.assertIsNone(meta[4])

    def test_02_new_audit_without_field_stays_null(self) -> None:
        audit = audit_service.create_audit(workplace_name="Bez data", year=2026)
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.expected_end_date)

    def test_03_create_stores_expected_end_date(self) -> None:
        expected = date(2026, 10, 3)
        audit = audit_service.create_audit(
            workplace_name="Nový",
            year=2026,
            started_at=date(2026, 9, 30),
            expected_end_date=expected,
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.expected_end_date, expected)
        self.assertEqual(loaded.started_at, date(2026, 9, 30))
        self.assertIsNone(loaded.finished_at)

    def test_04_update_and_clear_expected_end_date(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Úprava",
            year=2026,
            started_at=date(2026, 9, 30),
        )
        updated = audit_service.update_audit(
            audit.id,
            expected_end_date=date(2026, 10, 3),
        )
        assert updated is not None
        self.assertEqual(updated.expected_end_date, date(2026, 10, 3))
        cleared = audit_service.update_audit(audit.id, expected_end_date=None)
        assert cleared is not None
        self.assertIsNone(cleared.expected_end_date)
        self.assertEqual(cleared.started_at, date(2026, 9, 30))

    def test_05_repository_update_roundtrip(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Repo",
            year=2026,
            expected_end_date=date(2026, 11, 2),
        )
        audit.expected_end_date = date(2026, 11, 5)
        stored = audit_service.repository.update(audit)
        self.assertEqual(stored.expected_end_date, date(2026, 11, 5))
        stored.expected_end_date = None
        cleared = audit_service.repository.update(stored)
        self.assertIsNone(cleared.expected_end_date)

    def test_06_expected_end_without_start_stays_planned(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Jen konec",
            year=2026,
            expected_end_date=date(2026, 10, 3),
        )
        self.assertIsNone(audit.started_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PLANOVANO)
        self.assertEqual(
            audit_service.derive_status(audit.started_at, audit.finished_at),
            AUDIT_STATUS_PLANOVANO,
        )

    def test_07_expected_end_with_start_stays_in_progress(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Probíhá",
            year=2026,
            started_at=date(2026, 9, 30),
            expected_end_date=date(2026, 10, 3),
        )
        self.assertIsNone(audit.finished_at)
        self.assertEqual(audit.status, AUDIT_STATUS_PROBIHA)

    def test_08_finished_audit_ignores_expected_end(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Hotovo",
            year=2026,
            started_at=date(2026, 9, 30),
            expected_end_date=date(2026, 10, 3),
            finished_at=date(2026, 10, 2),
        )
        self.assertEqual(audit.status, AUDIT_STATUS_DOKONCENO)
        self.assertEqual(audit.expected_end_date, date(2026, 10, 3))
        self.assertEqual(audit.finished_at, date(2026, 10, 2))
        self.assertNotIn("expected_end", inspect.getsource(AuditService.derive_status))

    def test_09_expected_end_before_start_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            audit_service.create_audit(
                workplace_name="Dřív",
                year=2026,
                started_at=date(2026, 10, 3),
                expected_end_date=date(2026, 10, 1),
            )
        self.assertEqual(str(ctx.exception), AUDIT_EXPECTED_END_BEFORE_START_MESSAGE)
        self.assertEqual(audit_service.get_all(), [])

    def test_10_same_day_is_allowed(self) -> None:
        same = date(2026, 10, 3)
        audit = audit_service.create_audit(
            workplace_name="Stejný den",
            year=2026,
            started_at=same,
            expected_end_date=same,
        )
        self.assertEqual(audit.expected_end_date, same)
        self.assertEqual(audit.status, AUDIT_STATUS_PROBIHA)

    def _unfrozen(self, **fields):
        """Plán bez živé metodiky, aby dialog nenačítal celý strom otázek."""
        audit = audit_service.create_audit(**fields)
        stored = audit_service.repository.update_fields(
            audit.id,
            methodology_generation=AUDIT_METHODOLOGY_GENERATION_PLANNED_UNFROZEN_V1,
        )
        assert stored is not None
        return stored

    def test_11_ui_validation_shows_message_without_traceback(self) -> None:
        audit = self._unfrozen(
            workplace_name="UI validace",
            year=2026,
            started_at=date(2026, 10, 3),
        )
        dialog = AuditDialog(audit=audit)
        try:
            dialog.commission_widget.validate = lambda: (True, "")
            dialog.spis_widget.expected_end_date_edit.set_date_value(date(2026, 10, 1))
            with patch("moduly.audity.ui.audit_dialog.QMessageBox.warning") as warning:
                saved = dialog._persist()
            self.assertFalse(saved)
            self.assertTrue(warning.called)
            self.assertEqual(
                warning.call_args.args[2],
                AUDIT_EXPECTED_END_BEFORE_START_MESSAGE,
            )
            loaded = audit_service.get_by_id(audit.id)
            assert loaded is not None
            self.assertIsNone(loaded.expected_end_date)
            self.assertEqual(loaded.status, AUDIT_STATUS_PROBIHA)
        finally:
            dialog._closing = True
            dialog.close()
            dialog.deleteLater()

    def test_12_ui_saves_and_clears_expected_end(self) -> None:
        audit = self._unfrozen(
            workplace_name="UI uložení",
            year=2026,
            started_at=date(2026, 9, 30),
        )
        dialog = AuditDialog(audit=audit)
        try:
            dialog.commission_widget.validate = lambda: (True, "")
            dialog.save_commission_members = lambda *_args, **_kwargs: None
            dialog.spis_widget.expected_end_date_edit.set_date_value(date(2026, 10, 3))
            self.assertTrue(dialog._persist())
            loaded = audit_service.get_by_id(audit.id)
            assert loaded is not None
            self.assertEqual(loaded.expected_end_date, date(2026, 10, 3))
            dialog.spis_widget.expected_end_date_edit.clear_date()
            self.assertTrue(dialog._persist())
            cleared = audit_service.get_by_id(audit.id)
            assert cleared is not None
            self.assertIsNone(cleared.expected_end_date)
        finally:
            dialog._closing = True
            dialog.close()
            dialog.deleteLater()

    def test_13_unstarted_with_expected_end_is_hidden_from_agenda(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Nezahájený",
            year=2026,
            audit_date=date(2026, 9, 1),
            expected_end_date=date(2026, 9, 5),
        )
        ids = [
            item.source_id
            for item in get_attention_items(today=date(2026, 10, 4))
            if item.item_type == ITEM_TYPE_AUDIT
        ]
        self.assertNotIn(audit.id, ids)

    def test_14_started_without_expected_end_uses_started_at(self) -> None:
        started = date(2026, 9, 30)
        audit = audit_service.create_audit(
            workplace_name="Jen zahájení",
            year=2026,
            started_at=started,
        )
        item = next(
            row
            for row in get_attention_items(today=date(2026, 10, 1))
            if row.item_type == ITEM_TYPE_AUDIT and row.source_id == audit.id
        )
        self.assertEqual(item.date, started)
        self.assertFalse(attention_item_is_overdue(item, today=started))
        self.assertTrue(attention_item_is_overdue(item, today=date(2026, 10, 1)))

    def test_15_agenda_uses_expected_end_and_overdue_day_after(self) -> None:
        started = date(2026, 9, 30)
        expected = date(2026, 10, 3)
        audit = audit_service.create_audit(
            workplace_name="Vícedenní",
            year=2026,
            started_at=started,
            expected_end_date=expected,
        )
        item = next(
            row
            for row in get_attention_items(today=date(2026, 10, 3))
            if row.item_type == ITEM_TYPE_AUDIT and row.source_id == audit.id
        )
        self.assertEqual(item.date, expected)
        self.assertFalse(attention_item_is_overdue(item, today=date(2026, 10, 1)))
        self.assertFalse(attention_item_is_overdue(item, today=date(2026, 10, 3)))
        self.assertTrue(attention_item_is_overdue(item, today=date(2026, 10, 4)))

    def test_16_finished_audit_is_absent_from_agenda(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Dokončený",
            year=2026,
            started_at=date(2026, 9, 30),
            expected_end_date=date(2026, 10, 3),
            finished_at=date(2026, 10, 2),
        )
        ids = [
            item.source_id
            for item in get_attention_items(today=date(2026, 10, 4))
            if item.item_type == ITEM_TYPE_AUDIT
        ]
        self.assertNotIn(audit.id, ids)

    def test_17_other_agenda_item_types_keep_their_dates(self) -> None:
        task_due = date(2026, 10, 8)
        inspection_start = date(2026, 10, 6)
        task = task_service.create_task(title="Úkol beze změny", due_date=task_due)
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Prověrka beze změny",
            started_at=inspection_start,
        )
        audit_service.create_audit(
            workplace_name="Audit vedle",
            year=2026,
            started_at=date(2026, 9, 30),
            expected_end_date=date(2026, 10, 3),
        )
        items = {
            (item.item_type, item.source_id): item
            for item in get_attention_items(today=date(2026, 10, 1))
        }
        self.assertEqual(items[(ITEM_TYPE_TASK, task.id)].date, task_due)
        self.assertFalse(
            attention_item_is_overdue(items[(ITEM_TYPE_TASK, task.id)], today=date(2026, 10, 1))
        )
        self.assertEqual(items[(ITEM_TYPE_INSPECTION, inspection.id)].date, inspection_start)
        self.assertFalse(
            attention_item_is_overdue(
                items[(ITEM_TYPE_INSPECTION, inspection.id)],
                today=date(2026, 10, 1),
            )
        )
        task_service.cancel_task(task.id)
        bozp_inspection_service.delete_inspection(inspection.id)

    def test_18_apply_visit_context_does_not_copy_planned_date(self) -> None:
        widget = AuditSpisWidget()
        widget.expected_end_date_edit.set_date_value(date(2026, 1, 2))
        widget.apply_visit_context(
            SimpleNamespace(
                planned_year=2026,
                planned_month=4,
                planned_date=date(2026, 4, 15),
                workplace_id=None,
                workplace_name="Provoz",
            )
        )
        self.assertEqual(widget.audit_date_edit.get_date(), date(2026, 4, 15))
        self.assertIsNone(widget.started_at_edit.get_date())
        self.assertIsNone(widget.expected_end_date_edit.get_date())
        self.assertEqual(widget.status_label.text(), AUDIT_STATUS_PLANOVANO)
        labels = []
        for group in widget.findChildren(QGroupBox):
            if group.title() != "Termíny":
                continue
            form = group.layout()
            assert isinstance(form, QFormLayout)
            for row in range(form.rowCount()):
                label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                labels.append(label_item.widget().text())
        self.assertEqual(
            labels,
            [
                "Plánované datum:",
                "Datum zahájení:",
                "Předpokládané datum ukončení:",
            ],
        )
        widget.close()

    def test_19_widget_loads_value_into_get_data(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Načtení",
            year=2026,
            audit_date=date(2026, 9, 1),
            started_at=date(2026, 9, 30),
            expected_end_date=date(2026, 10, 3),
        )
        widget = AuditSpisWidget()
        widget.load_audit(audit)
        data = widget.get_data()
        self.assertEqual(data["audit_date"], date(2026, 9, 1))
        self.assertEqual(data["started_at"], date(2026, 9, 30))
        self.assertEqual(data["expected_end_date"], date(2026, 10, 3))
        self.assertEqual(widget.status_label.text(), AUDIT_STATUS_PROBIHA)
        widget.close()

    def test_20_startup_hook_calls_migration(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn("prepare_audit_expected_end_2_schema(", source)
        self.assertGreater(
            source.rfind("prepare_proverky_planned_section_summary_migration("),
            source.rfind("prepare_audit_proverky_section_note_schema("),
        )


class AuditExpectedEnd2MigrationTestCase(unittest.TestCase):
    def test_migration_adds_nullable_column_and_keeps_existing_null(self) -> None:
        workspace = Path(tempfile.mkdtemp(prefix="audit-expected-end-2-mig-"))
        database = workspace / "data.sqlite"
        connection = sqlite3.connect(str(database))
        try:
            connection.execute(
                """
                CREATE TABLE audits (
                    id INTEGER PRIMARY KEY,
                    number VARCHAR(30) DEFAULT '',
                    audit_date DATE,
                    started_at DATE,
                    finished_at DATE
                )
                """
            )
            connection.execute(
                "INSERT INTO audits (id, number, started_at) VALUES (1, '1/2026', '2026-09-30')"
            )
            connection.commit()
        finally:
            connection.close()

        self.assertTrue(needs_audit_expected_end_2_schema(database))
        result = prepare_audit_expected_end_2_schema(
            workspace_root=workspace,
            database_path=database,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(schema_is_present(database))
        self.assertFalse(needs_audit_expected_end_2_schema(database))

        meta = _column_meta(database, "expected_end_date")
        assert meta is not None
        self.assertEqual(str(meta[2]).upper(), "DATE")
        self.assertEqual(int(meta[3]), 0)
        self.assertIsNone(meta[4])

        connection = sqlite3.connect(str(database))
        try:
            row = connection.execute(
                "SELECT started_at, expected_end_date FROM audits WHERE id = 1"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row[0], "2026-09-30")
        self.assertIsNone(row[1])

        second = prepare_audit_expected_end_2_schema(
            workspace_root=workspace,
            database_path=database,
        )
        self.assertFalse(second.migrated)
        apply_audit_expected_end_2_schema_ddl(database)
        connection = sqlite3.connect(str(database))
        try:
            still_null = connection.execute(
                "SELECT expected_end_date FROM audits WHERE id = 1"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertIsNone(still_null)


if __name__ == "__main__":
    unittest.main()
