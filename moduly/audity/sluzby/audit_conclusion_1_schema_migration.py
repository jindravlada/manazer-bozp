"""AUDIT-CONCLUSION-1: aditivní sloupec conclusion_text na audits + záloha.

Pouze ADD COLUMN. Bez změny existujících dat, snapshotů ani výsledků.
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
)

logger = logging.getLogger(__name__)

TRANSITION_ID = "audit-conclusion-1"
BACKUP_NAME_PREFIX = "pre_audit_conclusion_1"

AUDIT_CONCLUSION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("conclusion_text", "conclusion_text TEXT"),
)


@dataclass(frozen=True)
class AuditConclusion1SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_conclusion_1_backup_path(
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
        "Nelze přidělit unikátní název zálohy AUDIT-CONCLUSION-1."
    )


def needs_audit_conclusion_1_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    connection = sqlite3.connect(str(path.resolve()))
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "audits" not in tables:
            return False
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(audits)").fetchall()
        }
        for column_name, _sql in AUDIT_CONCLUSION_COLUMNS:
            if column_name not in existing:
                return True
        return False
    finally:
        connection.close()


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_audit_conclusion_1_schema(path)


def apply_audit_conclusion_1_schema_ddl(db_path: Path) -> None:
    """Aditivní DDL v jedné transakci. Při chybě rollback."""
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(audits)").fetchall()
        }
        for column_name, column_sql in AUDIT_CONCLUSION_COLUMNS:
            if column_name in existing:
                continue
            connection.execute(f"ALTER TABLE audits ADD COLUMN {column_sql}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_conclusion_1_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> AuditConclusion1SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace AUDIT-CONCLUSION-1 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return AuditConclusion1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return AuditConclusion1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_audit_conclusion_1_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return AuditConclusion1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_audit_conclusion_1_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError as exc:
        raise MigrationGuardError(
            "Nepodařilo se vytvořit zálohu před migrací AUDIT-CONCLUSION-1."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_audit_conclusion_1_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace AUDIT-CONCLUSION-1 selhala. Obnovte data ze zálohy."
        ) from exc

    if not schema_is_present(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error="schema_not_present_after_ddl",
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace AUDIT-CONCLUSION-1 nedokončila schema. Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "AUDIT-CONCLUSION-1: schema OK, záloha %s",
        backup_path,
    )
    return AuditConclusion1SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
