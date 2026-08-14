"""AUDIT-EXTRAORDINARY-1: aditivní tabulky mimořádných otázek + záloha."""

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

TRANSITION_ID = "audit-extraordinary-1"
BACKUP_NAME_PREFIX = "pre_audit_extraordinary_1"

QUESTIONS_TABLE = "audit_extraordinary_questions"
TARGETS_TABLE = "audit_extraordinary_question_targets"

EXPECTED_TABLES = (QUESTIONS_TABLE, TARGETS_TABLE)
EXPECTED_INDEXES = (
    "ix_audit_extraordinary_questions_status",
    "ix_audit_extraordinary_targets_question_id",
    "ix_audit_extraordinary_targets_workplace_id",
    "ix_audit_extraordinary_targets_status",
    "uq_audit_extraordinary_question_target",
)

CREATE_QUESTIONS_SQL = """
CREATE TABLE IF NOT EXISTS audit_extraordinary_questions (
    id INTEGER NOT NULL PRIMARY KEY,
    question_text TEXT DEFAULT '' NOT NULL,
    assigned_by VARCHAR(200) DEFAULT '' NOT NULL,
    assigned_on DATE,
    note TEXT DEFAULT '' NOT NULL,
    status VARCHAR(30) DEFAULT 'active' NOT NULL,
    created_at DATETIME,
    updated_at DATETIME
)
"""

CREATE_TARGETS_SQL = """
CREATE TABLE IF NOT EXISTS audit_extraordinary_question_targets (
    id INTEGER NOT NULL PRIMARY KEY,
    question_id INTEGER NOT NULL,
    workplace_id INTEGER NOT NULL,
    status VARCHAR(30) DEFAULT 'pending' NOT NULL,
    assigned_audit_id INTEGER,
    verified_audit_id INTEGER,
    verified_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
)
"""

CREATE_INDEXES_SQL = (
    """
CREATE INDEX IF NOT EXISTS ix_audit_extraordinary_questions_status
ON audit_extraordinary_questions (status)
""",
    """
CREATE INDEX IF NOT EXISTS ix_audit_extraordinary_targets_question_id
ON audit_extraordinary_question_targets (question_id)
""",
    """
CREATE INDEX IF NOT EXISTS ix_audit_extraordinary_targets_workplace_id
ON audit_extraordinary_question_targets (workplace_id)
""",
    """
CREATE INDEX IF NOT EXISTS ix_audit_extraordinary_targets_status
ON audit_extraordinary_question_targets (status)
""",
    """
CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_extraordinary_question_target
ON audit_extraordinary_question_targets (question_id, workplace_id)
""",
)


@dataclass(frozen=True)
class AuditExtraordinarySchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_extraordinary_backup_path(
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
        "Nelze přidělit unikátní název zálohy AUDIT-EXTRAORDINARY-1."
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


def needs_audit_extraordinary_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, "audits"):
        return False
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
    return not needs_audit_extraordinary_schema(path)


def apply_audit_extraordinary_schema_ddl(db_path: Path) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(CREATE_QUESTIONS_SQL)
        connection.execute(CREATE_TARGETS_SQL)
        for sql in CREATE_INDEXES_SQL:
            connection.execute(sql)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_extraordinary_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> AuditExtraordinarySchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace AUDIT-EXTRAORDINARY-1 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return AuditExtraordinarySchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return AuditExtraordinarySchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_audit_extraordinary_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return AuditExtraordinarySchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_audit_extraordinary_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací AUDIT-EXTRAORDINARY-1. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_audit_extraordinary_schema_ddl(database_path)
        if not schema_is_present(database_path):
            raise MigrationGuardError(
                "AUDIT-EXTRAORDINARY-1: schema po DDL není kompletní."
            )
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error=str(exc),
        )
        raise MigrationGuardError(
            "Migrace AUDIT-EXTRAORDINARY-1 selhala. Data nebyla změněna "
            f"(ROLLBACK). Záloha: {backup_path}\n\n{exc}"
        ) from exc

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "AUDIT-EXTRAORDINARY-1: schema migrace dokončena, záloha=%s",
        backup_path,
    )
    return AuditExtraordinarySchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
