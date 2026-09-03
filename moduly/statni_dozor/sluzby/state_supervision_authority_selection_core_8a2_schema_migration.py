"""STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2: snapshot orgánu a pracoviště."""

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

TRANSITION_ID = "state-supervision-authority-selection-core-8a2"
BACKUP_NAME_PREFIX = "pre_state_supervision_authority_selection_"
SUPERVISIONS_TABLE = "state_supervisions"
AUTHORITY_ID_COLUMN = "authority_id"
OFFICE_NAME_SNAPSHOT_COLUMN = "authority_office_name_snapshot"
AUTHORITY_ID_INDEX = "ix_state_supervisions_authority_id"
AUTHORITY_OFFICE_ID_INDEX = "ix_state_supervisions_authority_office_id"


@dataclass(frozen=True)
class StateSupervisionAuthoritySelectionCore8a2SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_state_supervision_authority_selection_core_8a2_backup_path(
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
        "Nelze přidělit unikátní název zálohy "
        "STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2."
    )


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def _table_indexes(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA index_list("{table_name}")').fetchall()
    }


def needs_state_supervision_authority_selection_core_8a2_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, SUPERVISIONS_TABLE):
        return False
    connection = sqlite3.connect(str(path.resolve()))
    try:
        columns = _table_columns(connection, SUPERVISIONS_TABLE)
        if AUTHORITY_ID_COLUMN not in columns:
            return True
        if OFFICE_NAME_SNAPSHOT_COLUMN not in columns:
            return True
        indexes = _table_indexes(connection, SUPERVISIONS_TABLE)
        if AUTHORITY_ID_INDEX not in indexes:
            return True
        return False
    finally:
        connection.close()


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    if not sqlite_table_exists(path, SUPERVISIONS_TABLE):
        return False
    return not needs_state_supervision_authority_selection_core_8a2_schema(path)


def apply_state_supervision_authority_selection_core_8a2_schema_ddl(
    db_path: Path,
) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if SUPERVISIONS_TABLE in tables:
            columns = _table_columns(connection, SUPERVISIONS_TABLE)
            if AUTHORITY_ID_COLUMN not in columns:
                connection.execute(
                    "ALTER TABLE state_supervisions "
                    "ADD COLUMN authority_id INTEGER"
                )
            if OFFICE_NAME_SNAPSHOT_COLUMN not in columns:
                connection.execute(
                    "ALTER TABLE state_supervisions "
                    "ADD COLUMN authority_office_name_snapshot VARCHAR(250)"
                )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {AUTHORITY_ID_INDEX}
                ON state_supervisions ({AUTHORITY_ID_COLUMN})
                """
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_state_supervision_authority_selection_core_8a2_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> StateSupervisionAuthoritySelectionCore8a2SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2 "
            "nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return StateSupervisionAuthoritySelectionCore8a2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return StateSupervisionAuthoritySelectionCore8a2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_state_supervision_authority_selection_core_8a2_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return StateSupervisionAuthoritySelectionCore8a2SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_state_supervision_authority_selection_core_8a2_backup_path(
        backups_dir
    )
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError:
        raise
    except Exception as exc:  # pragma: no cover - obrana
        raise PreMigrationBackupError(
            "Nepodařilo se vytvořit zálohu před migrací "
            "STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2. Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_state_supervision_authority_selection_core_8a2_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2 selhala. "
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
            "Migrace STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2 nedokončila "
            "schema. Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "STATE-SUPERVISION-AUTHORITY-SELECTION-CORE-8A2: schema OK, záloha %s",
        backup_path,
    )
    return StateSupervisionAuthoritySelectionCore8a2SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
