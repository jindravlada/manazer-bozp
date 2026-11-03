"""AUDIT-INTRO-1: workplace_id existuje dřív než index ix_audits_workplace_id."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moduly.audity.sluzby import audit_intro_schema_migration as intro
from moduly.audity.sluzby.audit_intro_schema_migration import (
    apply_audit_intro_schema_ddl,
    needs_audit_intro_schema,
    prepare_audit_intro_schema,
)
from core.database.upgrade_guard import (
    MigrationGuardError,
    is_migration_in_progress,
    is_transition_complete,
    read_migration_state,
)


def _columns(db_path: Path) -> list[str]:
    connection = sqlite3.connect(str(db_path))
    try:
        return [
            str(row[1])
            for row in connection.execute("PRAGMA table_info(audits)").fetchall()
        ]
    finally:
        connection.close()


def _indexes(db_path: Path) -> set[str]:
    connection = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[1])
            for row in connection.execute("PRAGMA index_list(audits)").fetchall()
        }
    finally:
        connection.close()


def _audit_row(db_path: Path) -> tuple:
    connection = sqlite3.connect(str(db_path))
    try:
        return connection.execute(
            "SELECT id, title, note, workplace_id FROM audits WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()


def _write_legacy_audits(db_path: Path) -> None:
    """Tabulka audits ve tvaru reprezentativní databáze 3.1.0."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    try:
        connection.executescript(
            """
            CREATE TABLE audits (
                id INTEGER PRIMARY KEY,
                audit_date DATE,
                title VARCHAR(250) DEFAULT '',
                note TEXT DEFAULT ''
            );
            CREATE TABLE attachments (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                stored_path TEXT,
                original_path TEXT,
                filename VARCHAR(250)
            );
            """
        )
        connection.execute(
            "INSERT INTO audits(title, note) VALUES (?, ?)",
            ("Audit BOZP", "Interní audit"),
        )
        connection.execute(
            "INSERT INTO attachments(entity_type, entity_id, stored_path, "
            "original_path, filename) VALUES (?, ?, ?, ?, ?)",
            (
                "accident",
                1,
                "accident/1/Protokol.pdf",
                "/import/originál.pdf",
                "Protokol.pdf",
            ),
        )
        connection.commit()
    finally:
        connection.close()


class AuditIntroWorkplaceColumnTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="audit-intro-wp-"))
        self.db = self.root / "databaze" / "manager_bozp.db"
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "konfigurace").mkdir()
        (self.workspace / "zalohy").mkdir()
        self.settings = self.workspace / "konfigurace" / "settings.json"
        self.settings.write_text('{"jazyk": "cs"}\n', encoding="utf-8")
        attachment = self.workspace / "prilohy" / "accident" / "1"
        attachment.mkdir(parents=True)
        (attachment / "Protokol.pdf").write_bytes(b"%PDF-310")

    def test_legacy_3_1_0_gains_column_and_index_without_rewriting_rows(self) -> None:
        _write_legacy_audits(self.db)
        self.assertNotIn("workplace_id", _columns(self.db))

        apply_audit_intro_schema_ddl(self.db)
        apply_audit_intro_schema_ddl(self.db)

        self.assertEqual(_columns(self.db).count("workplace_id"), 1)
        self.assertIn("changes_since_last", _columns(self.db))
        self.assertIn("ix_audits_workplace_id", _indexes(self.db))
        self.assertEqual(_audit_row(self.db), (1, "Audit BOZP", "Interní audit", None))
        connection = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT id, entity_id, stored_path, filename FROM attachments"
                ).fetchone(),
                (1, 1, "accident/1/Protokol.pdf", "Protokol.pdf"),
            )
        finally:
            connection.close()
        self.assertEqual(
            (self.workspace / "prilohy" / "accident" / "1" / "Protokol.pdf").read_bytes(),
            b"%PDF-310",
        )
        self.assertFalse(needs_audit_intro_schema(self.db))

    def test_existing_workplace_id_value_is_kept(self) -> None:
        self.db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db))
        try:
            connection.execute(
                """
                CREATE TABLE audits (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) DEFAULT '',
                    note TEXT DEFAULT '',
                    workplace_id INTEGER,
                    changes_since_last TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO audits(id, title, note, workplace_id, changes_since_last) "
                "VALUES (1, ?, ?, ?, ?)",
                ("Audit z 4.1.3", "beze změny", 12, "původní text"),
            )
            connection.execute(
                "CREATE INDEX ix_audits_workplace_id ON audits (workplace_id)"
            )
            connection.commit()
        finally:
            connection.close()

        def snapshot() -> list[tuple]:
            connection = sqlite3.connect(str(self.db))
            try:
                return connection.execute(
                    "SELECT id, title, note, workplace_id, changes_since_last "
                    "FROM audits"
                ).fetchall()
            finally:
                connection.close()

        before = snapshot()
        apply_audit_intro_schema_ddl(self.db)
        after = snapshot()
        self.assertEqual(after, before)
        self.assertEqual(after, [(1, "Audit z 4.1.3", "beze změny", 12, "původní text")])
        self.assertEqual(_columns(self.db).count("workplace_id"), 1)

    def test_existing_column_without_index_is_not_added_again(self) -> None:
        self.db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db))
        try:
            connection.execute(
                """
                CREATE TABLE audits (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) DEFAULT '',
                    workplace_id INTEGER
                )
                """
            )
            connection.execute(
                "INSERT INTO audits(id, title, workplace_id) VALUES (1, ?, ?)",
                ("Audit se sloupcem", 7),
            )
            connection.commit()
        finally:
            connection.close()

        apply_audit_intro_schema_ddl(self.db)

        self.assertEqual(_columns(self.db).count("workplace_id"), 1)
        connection = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT id, title, workplace_id FROM audits WHERE id = 1"
                ).fetchone(),
                (1, "Audit se sloupcem", 7),
            )
        finally:
            connection.close()
        self.assertIn("ix_audits_workplace_id", _indexes(self.db))
        self.assertIn("changes_since_last", _columns(self.db))

    def test_failed_index_rolls_back_and_is_not_marked_complete(self) -> None:
        _write_legacy_audits(self.db)
        with patch.object(
            intro,
            "CREATE_AUDITS_WORKPLACE_INDEX_SQL",
            "CREATE INDEX IF NOT EXISTS ix_audits_workplace_id "
            "ON audits (missing_column_zzz)",
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_intro_schema(
                    workspace_root=self.workspace,
                    database_path=self.db,
                    settings_path=self.settings,
                )

        self.assertNotIn("workplace_id", _columns(self.db))
        self.assertNotIn("changes_since_last", _columns(self.db))
        connection = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT id, title, note FROM audits"
                ).fetchone(),
                (1, "Audit BOZP", "Interní audit"),
            )
        finally:
            connection.close()
        self.assertFalse(is_transition_complete(self.workspace, intro.TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.workspace, intro.TRANSITION_ID))
        failed = read_migration_state(self.workspace).get("last_failed") or {}
        self.assertEqual(failed.get("transition_id"), intro.TRANSITION_ID)
        self.assertIn("missing_column_zzz", str(failed.get("error")))

        result = prepare_audit_intro_schema(
            workspace_root=self.workspace,
            database_path=self.db,
            settings_path=self.settings,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(is_transition_complete(self.workspace, intro.TRANSITION_ID))
        self.assertEqual(_audit_row(self.db), (1, "Audit BOZP", "Interní audit", None))
        connection = sqlite3.connect(str(self.db))
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0],
                1,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
