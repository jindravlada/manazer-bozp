"""AUDIT-EXTRAORDINARY-3: aditivní sloupec verification_type + záloha."""

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

TRANSITION_ID = "audit-extraordinary-3"
BACKUP_NAME_PREFIX = "pre_audit_extraordinary_3"

QUESTIONS_TABLE = "audit_extraordinary_questions"

EXTRAORDINARY_3_COLUMNS: tuple[tuple[str, str], ...] = (
    ("verification_type", "verification_type VARCHAR(40)"),
)


@dataclass(frozen=True)
class AuditExtraordinary3SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_extraordinary_3_backup_path(
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
        "Nelze přidělit unikátní název zálohy AUDIT-EXTRAORDINARY-3."
    )


def _table_columns(db_path: Path, table: str) -> set[str]:
    path = Path(db_path)
    if not path.is_file():
        return set()
    connection = sqlite3.connect(str(path.resolve()))
    try:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows if row[1]}
    finally:
        connection.close()


def needs_audit_extraordinary_3_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, QUESTIONS_TABLE):
        return False
    columns = _table_columns(path, QUESTIONS_TABLE)
    for name, _ddl in EXTRAORDINARY_3_COLUMNS:
        if name not in columns:
            return True
    return False


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    if not sqlite_table_exists(path, QUESTIONS_TABLE):
        return False
    return not needs_audit_extraordinary_3_schema(path)


def apply_audit_extraordinary_3_schema_ddl(db_path: Path) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = {
            str(row[1])
            for row in connection.execute(
                f"PRAGMA table_info({QUESTIONS_TABLE})"
            ).fetchall()
            if row[1]
        }
        for name, ddl in EXTRAORDINARY_3_COLUMNS:
            if name in existing:
                continue
            connection.execute(
                f"ALTER TABLE {QUESTIONS_TABLE} ADD COLUMN {ddl}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_extraordinary_3_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> AuditExtraordinary3SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace AUDIT-EXTRAORDINARY-3 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return AuditExtraordinary3SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return AuditExtraordinary3SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not sqlite_table_exists(database_path, QUESTIONS_TABLE):
        return AuditExtraordinary3SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="extraordinary_1_missing",
        )

    if not needs_audit_extraordinary_3_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return AuditExtraordinary3SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_audit_extraordinary_3_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací AUDIT-EXTRAORDINARY-3. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_audit_extraordinary_3_schema_ddl(database_path)
        if not schema_is_present(database_path):
            raise MigrationGuardError(
                "AUDIT-EXTRAORDINARY-3: schema po DDL není kompletní."
            )
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error=str(exc),
        )
        raise MigrationGuardError(
            "Migrace AUDIT-EXTRAORDINARY-3 selhala. Data nebyla změněna "
            f"(ROLLBACK). Záloha: {backup_path}\n\n{exc}"
        ) from exc

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "AUDIT-EXTRAORDINARY-3: schema migrace dokončena, záloha=%s",
        backup_path,
    )
    return AuditExtraordinary3SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
