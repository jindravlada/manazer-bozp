"""AUDIT-SNAPSHOT-0: záloha, aditivní migrace, snapshot service bez auto-použití."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _seed_legacy_audits_db(db_path: Path) -> None:
    """Minimální DB se stávajícími audit tabulkami bez snapshot infrastruktury."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE audits (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                year INTEGER,
                planned_month INTEGER,
                audit_date DATE,
                started_at DATE,
                finished_at DATE,
                status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL,
                audit_type VARCHAR(30) DEFAULT 'Řádný' NOT NULL,
                workplace_id INTEGER,
                workplace_name VARCHAR(150) DEFAULT '',
                title VARCHAR(250) DEFAULT '',
                program_id INTEGER,
                program_visit_id INTEGER,
                silne_stranky TEXT DEFAULT '' NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE control_results (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                source_area_id VARCHAR(80) DEFAULT '',
                source_area_label VARCHAR(150) DEFAULT '',
                source_section_id VARCHAR(80) DEFAULT '',
                source_section_label VARCHAR(150) DEFAULT '',
                source_control_point_id VARCHAR(80) DEFAULT '',
                source_control_point_label VARCHAR(200) DEFAULT '',
                result VARCHAR(40) DEFAULT 'nekontrolovano' NOT NULL,
                note TEXT DEFAULT '',
                shared_experience BOOLEAN DEFAULT 0 NOT NULL,
                photo_path VARCHAR(500) DEFAULT '',
                recorded_by_name VARCHAR(150) DEFAULT '',
                recorded_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE findings (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                finding_type VARCHAR(30) DEFAULT 'zjisteni' NOT NULL,
                reference_label VARCHAR(100) DEFAULT '',
                description TEXT DEFAULT '',
                source_area_label VARCHAR(150) DEFAULT '',
                source_section_label VARCHAR(150) DEFAULT '',
                source_control_point_id VARCHAR(80) DEFAULT '',
                source_control_point_label VARCHAR(200) DEFAULT '',
                recommended_action TEXT DEFAULT '',
                due_date DATE,
                responsible_person_id INTEGER,
                responsible_person_name VARCHAR(150) DEFAULT '',
                status VARCHAR(30) DEFAULT 'otevrene' NOT NULL,
                resolved_at DATE,
                resolution_note TEXT DEFAULT '',
                display_order INTEGER DEFAULT 0 NOT NULL,
                task_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                description TEXT DEFAULT '',
                workplace_id INTEGER,
                workplace_name VARCHAR(150) DEFAULT '',
                responsible_person VARCHAR(150) DEFAULT '',
                due_date DATE,
                completed INTEGER DEFAULT 0,
                canceled INTEGER DEFAULT 0,
                source_module VARCHAR(50) DEFAULT 'manual',
                source_record_id INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE audit_programs (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                name VARCHAR(250) DEFAULT '',
                date_from DATE,
                date_to DATE,
                status VARCHAR(30) DEFAULT 'draft' NOT NULL,
                standards_json TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at DATETIME,
                approved_at DATETIME,
                closed_at DATETIME,
                manual_planning BOOLEAN DEFAULT 0 NOT NULL,
                previous_program_id INTEGER
            );
            INSERT INTO audits (id, number, year, title, status, silne_stranky)
            VALUES (1, '1/2026', 2026, 'Legacy audit', 'Probíhá', '');
            INSERT INTO control_results (
                id, entity_type, entity_id, source_area_label, source_section_label,
                source_control_point_id, source_control_point_label, result
            ) VALUES (
                1, 'audity', 1, 'Proces', 'Sekce', 'q1', 'Tvrzení legacy', 'vyhovuje'
            );
            INSERT INTO findings (
                id, entity_type, entity_id, description, status
            ) VALUES (1, 'audity', 1, 'Zjištění legacy', 'otevrene');
            INSERT INTO tasks (id, description, source_module, source_record_id)
            VALUES (1, 'Úkol legacy', 'finding', 1);
            INSERT INTO audit_programs (id, number, name, status)
            VALUES (1, 'P-1', 'Program legacy', 'running');
            """
        )
        conn.commit()
    finally:
        conn.close()


_MIG_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-0-mig-"))
_MIG_HOME_PATCHER = patch.object(Path, "home", return_value=_MIG_HOME)
_MIG_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()
_MIG_WS = storage_module.storage_service.base

import core.database.session as session_module

importlib.reload(session_module)

from core.database.upgrade_guard import (  # noqa: E402
    MigrationGuardError,
    PreMigrationBackupError,
    is_migration_failed,
    is_migration_in_progress,
    is_transition_complete,
    read_migration_state,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import (  # noqa: E402
    AUDIT_SNAPSHOT_COLUMNS,
    AUDIT_SNAPSHOT_TABLE,
    TRANSITION_ID,
    allocate_audit_snapshot_backup_path,
    apply_audit_snapshot_schema_ddl,
    needs_audit_snapshot_schema,
    prepare_audit_snapshot_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class AuditSnapshot0MigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_MIG_HOME)
        self._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

        self.db_path = storage_module.storage_service.database_path
        self.ws = storage_module.storage_service.base
        state_path = self.ws / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        for backup in (self.ws / "zalohy").glob("pre_audit_snapshot_migration_*"):
            backup.unlink()
        _seed_legacy_audits_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_migration_creates_expected_structures_only(self) -> None:
        before_tables = {
            row[0]
            for row in sqlite3.connect(str(self.db_path))
            .execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            .fetchall()
        }

        result = prepare_audit_snapshot_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )

        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(
                "pre_audit_snapshot_migration_"
            )
        )
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))

        after_tables = {
            row[0]
            for row in sqlite3.connect(str(self.db_path))
            .execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            .fetchall()
        }
        self.assertEqual(after_tables - before_tables, {AUDIT_SNAPSHOT_TABLE})
        columns = _table_columns(self.db_path, "audits")
        for name, _sql in AUDIT_SNAPSHOT_COLUMNS:
            self.assertIn(name, columns)

    def test_migration_preserves_existing_row_counts(self) -> None:
        counts_before = {
            "audits": _count(self.db_path, "audits"),
            "control_results": _count(self.db_path, "control_results"),
            "findings": _count(self.db_path, "findings"),
            "tasks": _count(self.db_path, "tasks"),
            "audit_programs": _count(self.db_path, "audit_programs"),
        }

        prepare_audit_snapshot_schema(
            workspace_root=self.ws, database_path=self.db_path
        )

        for table, expected in counts_before.items():
            self.assertEqual(_count(self.db_path, table), expected)
        self.assertEqual(_count(self.db_path, AUDIT_SNAPSHOT_TABLE), 0)

        row = sqlite3.connect(str(self.db_path)).execute(
            "SELECT title, methodology_source, questions_frozen_at, methodology_generation "
            "FROM audits WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "Legacy audit")
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])
        self.assertIsNone(row[3])

    def test_migration_is_idempotent(self) -> None:
        first = prepare_audit_snapshot_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_after_first = list(
            (self.ws / "zalohy").glob("pre_audit_snapshot_migration_*")
        )
        self.assertEqual(len(backups_after_first), 1)

        second = prepare_audit_snapshot_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_after_second = list(
            (self.ws / "zalohy").glob("pre_audit_snapshot_migration_*")
        )
        self.assertEqual(len(backups_after_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_after_second[0])

    def test_backup_failure_blocks_migration(self) -> None:
        with patch(
            "moduly.audity.sluzby.audit_snapshot_schema_migration.create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_audit_snapshot_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )

        self.assertTrue(needs_audit_snapshot_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(
            {
                row[0]
                for row in sqlite3.connect(str(self.db_path))
                .execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
                .fetchall()
            },
            {
                "audits",
                "control_results",
                "findings",
                "tasks",
                "audit_programs",
            },
        )

    def test_ddl_failure_rolls_back_and_is_not_complete(self) -> None:
        def boom(_db_path: Path) -> None:
            raise RuntimeError("umělá chyba DDL")

        with patch(
            "moduly.audity.sluzby.audit_snapshot_schema_migration.apply_audit_snapshot_schema_ddl",
            side_effect=boom,
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_snapshot_schema(
                    workspace_root=self.ws, database_path=self.db_path
                )

        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertTrue(needs_audit_snapshot_schema(self.db_path))
        backups = list((self.ws / "zalohy").glob("pre_audit_snapshot_migration_*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].is_file())
        state = read_migration_state(self.ws)
        self.assertEqual(state["last_failed"]["transition_id"], TRANSITION_ID)

    def test_transactional_ddl_rollback_on_mid_failure(self) -> None:
        real_connect = sqlite3.connect

        class FlakyConnection:
            def __init__(self, path: str):
                self._conn = real_connect(path)
                self._alter_count = 0

            def execute(self, sql, *args, **kwargs):
                text_sql = str(sql)
                if text_sql.startswith("ALTER TABLE audits ADD COLUMN"):
                    self._alter_count += 1
                    if self._alter_count >= 2:
                        raise sqlite3.OperationalError("umělá chyba ALTER")
                return self._conn.execute(sql, *args, **kwargs)

            def commit(self):
                return self._conn.commit()

            def rollback(self):
                return self._conn.rollback()

            def close(self):
                return self._conn.close()

        def connect_flaky(path, *args, **kwargs):
            if "mode=ro" in str(path) or kwargs.get("uri"):
                return real_connect(path, *args, **kwargs)
            return FlakyConnection(str(path))

        with patch(
            "moduly.audity.sluzby.audit_snapshot_schema_migration.sqlite3.connect",
            side_effect=connect_flaky,
        ):
            with self.assertRaises(sqlite3.OperationalError):
                apply_audit_snapshot_schema_ddl(self.db_path)

        self.assertTrue(needs_audit_snapshot_schema(self.db_path))
        tables = {
            row[0]
            for row in real_connect(str(self.db_path))
            .execute("SELECT name FROM sqlite_master WHERE type='table'")
            .fetchall()
        }
        self.assertNotIn(AUDIT_SNAPSHOT_TABLE, tables)

    def test_allocate_backup_path_never_overwrites(self) -> None:
        zalohy = self.ws / "zalohy"
        zalohy.mkdir(parents=True, exist_ok=True)
        first = allocate_audit_snapshot_backup_path(zalohy)
        first.write_text("x", encoding="utf-8")
        second = allocate_audit_snapshot_backup_path(zalohy)
        self.assertNotEqual(first, second)
        self.assertFalse(second.exists())


_SVC_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-0-svc-"))
_SVC_HOME_PATCHER = patch.object(Path, "home", return_value=_SVC_HOME)
_SVC_HOME_PATCHER.start()

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()
importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import initialize_database  # noqa: E402

initialize_database()

from core.shared.constants import ENTITY_AUDITY  # noqa: E402
from core.shared.sluzby.control_result_service import (  # noqa: E402
    ControlPointContext,
    control_result_service,
)
from core.shared.sluzby.finding_service import finding_service  # noqa: E402
from moduly.audity.sluzby.audit_question_snapshot_service import (  # noqa: E402
    audit_question_snapshot_service,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_verification_service import (  # noqa: E402
    audit_verification_service,
)

_SVC_HOME_PATCHER.stop()
_SVC_WS = storage_module.storage_service.base
_SVC_DB = storage_module.storage_service.database_path


class AuditSnapshot0ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_SVC_HOME)
        self._home.start()
        importlib.reload(storage_module)
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    def tearDown(self) -> None:
        self._home.stop()

    def test_build_snapshot_respects_planned_processes(self) -> None:
        processes = audit_knowledge_service.get_processes(ensure=True)
        with_file = [p for p in processes if p.has_knowledge_file]
        self.assertGreaterEqual(len(with_file), 2)
        first = with_file[0]
        second = with_file[1]

        audit = audit_service.create_audit(title="Snapshot build")
        all_drafts = audit_question_snapshot_service.build_snapshot_for_audit(
            audit.id, planned_process_ids=None, ensure=True
        )
        filtered = audit_question_snapshot_service.build_snapshot_for_audit(
            audit.id, planned_process_ids={first.id}, ensure=False
        )

        self.assertGreater(len(all_drafts), 0)
        self.assertGreater(len(filtered), 0)
        self.assertTrue(all(d.process_id == first.id for d in filtered))
        self.assertTrue(any(d.process_id == second.id for d in all_drafts))
        self.assertTrue(all(d.assertion_text for d in filtered))
        self.assertTrue(all(d.verification_type for d in filtered))
        self.assertEqual(_count(_SVC_DB, AUDIT_SNAPSHOT_TABLE), 0)

        sample = filtered[0]
        target = (
            "teren"
            if sample.verification_type != "teren"
            else "dokumentace"
        )
        audit_verification_service.set_override(
            audit.id,
            area_id=sample.process_id,
            section_id=sample.section_id,
            control_point_id=sample.assertion_id,
            verification_type=target,
        )
        after_override = audit_question_snapshot_service.build_snapshot_for_audit(
            audit.id, planned_process_ids={first.id}, ensure=False
        )
        matched = [
            d
            for d in after_override
            if d.assertion_id == sample.assertion_id
            and d.section_id == sample.section_id
        ]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].verification_type, target)

    def test_build_snapshot_ensure_catalogs_once(self) -> None:
        audit = audit_service.create_audit(title="Ensure once")
        ensure_calls = {"count": 0}
        original = audit_knowledge_service.ensure_catalogs

        def counting_ensure() -> None:
            ensure_calls["count"] += 1
            return original()

        with patch.object(
            audit_knowledge_service, "ensure_catalogs", side_effect=counting_ensure
        ):
            drafts = audit_question_snapshot_service.build_snapshot_for_audit(
                audit.id, ensure=True
            )
        self.assertGreater(len(drafts), 0)
        self.assertEqual(ensure_calls["count"], 1)


class AuditSnapshot0RegressionSmokeTestCase(unittest.TestCase):
    """AuditDialog / exporty / data path zůstávají bez snapshot napojení."""

    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_SVC_HOME)
        self._home.start()
        importlib.reload(storage_module)
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    def tearDown(self) -> None:
        self._home.stop()

    def test_existing_audit_rows_unchanged_by_service(self) -> None:
        audit = audit_service.create_audit(title="Bez snapshotu")
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="p",
                area_label="P",
                section_id="s",
                section_label="S",
                control_point_id="q",
                control_point_label="Otázka",
            ),
            result="vyhovuje",
        )
        finding_service.create(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            description="Zjištění",
        )
        audits_before = _count(_SVC_DB, "audits")
        results_before = _count(_SVC_DB, "control_results")
        findings_before = _count(_SVC_DB, "findings")

        audit_question_snapshot_service.build_snapshot_for_audit(audit.id, ensure=True)

        reloaded = audit_service.get_by_id(audit.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.title, "Bez snapshotu")
        self.assertIsNone(reloaded.methodology_source)
        self.assertEqual(_count(_SVC_DB, "audits"), audits_before)
        self.assertEqual(_count(_SVC_DB, "control_results"), results_before)
        self.assertEqual(_count(_SVC_DB, "findings"), findings_before)
        self.assertEqual(_count(_SVC_DB, AUDIT_SNAPSHOT_TABLE), 0)


if __name__ == "__main__":
    unittest.main()
