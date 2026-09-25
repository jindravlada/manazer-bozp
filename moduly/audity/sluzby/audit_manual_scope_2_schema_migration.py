"""AUDIT-MANUAL-SCOPE-2: tabulka rozsahu ručního auditu.

Pouze CREATE TABLE. Existující audity a snapshoty se nepřepisují.
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

TRANSITION_ID = "audit-manual-scope-2"
BACKUP_NAME_PREFIX = "pre_audit_manual_scope_2"
TABLE_NAME = "audit_scope_processes"
INDEX_NAME = "ix_audit_scope_processes_audit_id"
UNIQUE_NAME = "uq_audit_scope_processes_audit_process"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_scope_processes (
    id INTEGER NOT NULL PRIMARY KEY,
    audit_id INTEGER NOT NULL,
    process_id VARCHAR(80) DEFAULT '' NOT NULL,
    process_name VARCHAR(250) DEFAULT '' NOT NULL,
    display_order INTEGER DEFAULT 0 NOT NULL
)
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_audit_scope_processes_audit_id
ON audit_scope_processes (audit_id)
"""

CREATE_UNIQUE_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_scope_processes_audit_process
ON audit_scope_processes (audit_id, process_id)
"""


@dataclass(frozen=True)
class AuditManualScope2SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_manual_scope_2_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    root = Path(backups_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{BACKUP_NAME_PREFIX}_{stamp}{BACKUP_EXTENSION}"
    candidate = root / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = root / f"{BACKUP_NAME_PREFIX}_{stamp}_{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise MigrationGuardError(
        "Nelze přidělit unikátní název zálohy AUDIT-MANUAL-SCOPE-2."
    )


def _index_names(db_path: Path) -> set[str]:
    connection = sqlite3.connect(str(Path(db_path).resolve()))
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        return {str(row[0]) for row in rows if row[0]}
    finally:
        connection.close()


def needs_audit_manual_scope_2_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, "audits"):
        return False
    if not sqlite_table_exists(path, TABLE_NAME):
        return True
    indexes = _index_names(path)
    return INDEX_NAME not in indexes or UNIQUE_NAME not in indexes


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_audit_manual_scope_2_schema(path)


def apply_audit_manual_scope_2_schema_ddl(db_path: Path) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(CREATE_TABLE_SQL)
        connection.execute(CREATE_INDEX_SQL)
        connection.execute(CREATE_UNIQUE_SQL)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_manual_scope_2_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> AuditManualScope2SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace AUDIT-MANUAL-SCOPE-2 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return AuditManualScope2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return AuditManualScope2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_audit_manual_scope_2_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return AuditManualScope2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_audit_manual_scope_2_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací AUDIT-MANUAL-SCOPE-2. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_audit_manual_scope_2_schema_ddl(database_path)
        if not schema_is_present(database_path):
            raise MigrationGuardError(
                "AUDIT-MANUAL-SCOPE-2: schema po DDL není kompletní."
            )
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error=str(exc),
        )
        raise MigrationGuardError(
            "Migrace AUDIT-MANUAL-SCOPE-2 selhala. Data nebyla změněna "
            f"(ROLLBACK). Záloha: {backup_path}\n\n{exc}"
        ) from exc

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "AUDIT-MANUAL-SCOPE-2: schema migrace dokončena, záloha=%s",
        backup_path,
    )
    return AuditManualScope2SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
