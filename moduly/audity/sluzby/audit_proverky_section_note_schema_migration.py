"""AUDIT-PROVERKY-SECTION-NOTE-1: režim poznámek + tabulky souhrnných sdělení.

Aditivní DDL v jedné transakci. Existující Audity/Prověrky zůstávají na
``notes_mode IS NULL`` (legacy). Žádný backfill poznámek.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.backup.constants import BACKUP_EXTENSION
from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    create_verified_pre_migration_backup,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_failed,
    mark_migration_in_progress,
    read_migration_state,
    sqlite_table_exists,
)

logger = logging.getLogger(__name__)

TRANSITION_ID = "audit-proverky-section-note-1"
BACKUP_NAME_PREFIX = "pre_audit_proverky_section_note_"

NOTES_MODE_SQL = "notes_mode VARCHAR(40)"

AUDIT_SUMMARIES_TABLE = "audit_section_summaries"
INSPECTION_SUMMARIES_TABLE = "inspection_section_summaries"

EXPECTED_TABLES = (AUDIT_SUMMARIES_TABLE, INSPECTION_SUMMARIES_TABLE)
EXPECTED_INDEXES = (
    "ix_audit_section_summaries_audit_id",
    "uq_audit_section_summaries_key",
    "ix_inspection_section_summaries_inspection_id",
    "uq_inspection_section_summaries_key",
)

CREATE_AUDIT_SUMMARIES_SQL = """
CREATE TABLE IF NOT EXISTS audit_section_summaries (
    id INTEGER NOT NULL PRIMARY KEY,
    audit_id INTEGER NOT NULL,
    process_id VARCHAR(80) DEFAULT '' NOT NULL,
    section_id VARCHAR(80) DEFAULT '' NOT NULL,
    summary_text TEXT DEFAULT '' NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
)
"""

CREATE_INSPECTION_SUMMARIES_SQL = """
CREATE TABLE IF NOT EXISTS inspection_section_summaries (
    id INTEGER NOT NULL PRIMARY KEY,
    inspection_id INTEGER NOT NULL,
    area_id VARCHAR(80) DEFAULT '' NOT NULL,
    section_id VARCHAR(80) DEFAULT '' NOT NULL,
    summary_text TEXT DEFAULT '' NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
)
"""

CREATE_INDEXES_SQL = (
    """
CREATE INDEX IF NOT EXISTS ix_audit_section_summaries_audit_id
ON audit_section_summaries (audit_id)
""",
    """
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_section_summaries_key
ON audit_section_summaries (audit_id, process_id, section_id)
""",
    """
CREATE INDEX IF NOT EXISTS ix_inspection_section_summaries_inspection_id
ON inspection_section_summaries (inspection_id)
""",
    """
CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_section_summaries_key
ON inspection_section_summaries (inspection_id, area_id, section_id)
""",
)


@dataclass(frozen=True)
class AuditProverkySectionNoteSchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_proverky_section_note_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    root = Path(backups_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{BACKUP_NAME_PREFIX}{stamp}{BACKUP_EXTENSION}"
    candidate = root / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = root / f"{BACKUP_NAME_PREFIX}{stamp}_{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise MigrationGuardError(
        "Nelze přidělit unikátní název zálohy AUDIT-PROVERKY-SECTION-NOTE-1."
    )


def _list_indexes(db_path: Path) -> set[str]:
    path = Path(db_path)
    if not path.is_file():
        return set()
    connection = sqlite3.connect(str(path.resolve()))
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        return {str(row[0]) for row in rows if row[0]}
    finally:
        connection.close()


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if table not in tables:
        return set()
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def needs_audit_proverky_section_note_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, "audits") and not sqlite_table_exists(
        path, "bozp_inspections"
    ):
        return False
    connection = sqlite3.connect(str(path.resolve()))
    try:
        if sqlite_table_exists(path, "audits"):
            if "notes_mode" not in _table_columns(connection, "audits"):
                return True
        if sqlite_table_exists(path, "bozp_inspections"):
            if "notes_mode" not in _table_columns(connection, "bozp_inspections"):
                return True
    finally:
        connection.close()
    for table in EXPECTED_TABLES:
        if not sqlite_table_exists(path, table):
            return True
    indexes = _list_indexes(path)
    for name in EXPECTED_INDEXES:
        if name not in indexes:
            return True
    return False


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_audit_proverky_section_note_schema(path)


def apply_audit_proverky_section_note_schema_ddl(db_path: Path) -> None:
    """Aditivní DDL v jedné transakci. Při chybě rollback, bez backfillu."""
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "audits" in tables:
            audit_cols = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(audits)").fetchall()
            }
            if "notes_mode" not in audit_cols:
                connection.execute(f"ALTER TABLE audits ADD COLUMN {NOTES_MODE_SQL}")
        if "bozp_inspections" in tables:
            inspection_cols = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(bozp_inspections)"
                ).fetchall()
            }
            if "notes_mode" not in inspection_cols:
                connection.execute(
                    f"ALTER TABLE bozp_inspections ADD COLUMN {NOTES_MODE_SQL}"
                )
        connection.execute(CREATE_AUDIT_SUMMARIES_SQL)
        connection.execute(CREATE_INSPECTION_SUMMARIES_SQL)
        for sql in CREATE_INDEXES_SQL:
            connection.execute(sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_proverky_section_note_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> AuditProverkySectionNoteSchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace AUDIT-PROVERKY-SECTION-NOTE-1 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return AuditProverkySectionNoteSchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return AuditProverkySectionNoteSchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_audit_proverky_section_note_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return AuditProverkySectionNoteSchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_audit_proverky_section_note_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací "
            "AUDIT-PROVERKY-SECTION-NOTE-1."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_audit_proverky_section_note_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace AUDIT-PROVERKY-SECTION-NOTE-1 selhala. "
            "Obnovte data ze zálohy."
        ) from exc

    if not schema_is_present(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error="schema_not_present_after_ddl",
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace AUDIT-PROVERKY-SECTION-NOTE-1 nedokončila schema. "
            "Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "AUDIT-PROVERKY-SECTION-NOTE-1: schema OK, záloha %s",
        backup_path,
    )
    return AuditProverkySectionNoteSchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
