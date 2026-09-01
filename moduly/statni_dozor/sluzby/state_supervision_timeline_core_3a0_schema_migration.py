"""STATE-SUPERVISION-TIMELINE-CORE-3A0: aditivní schema průběhu kontroly."""

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

TRANSITION_ID = "state-supervision-timeline-core-3a0"
BACKUP_NAME_PREFIX = "pre_state_supervision_timeline"
TABLE_NAME = "state_supervision_timeline_items"

DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS state_supervision_timeline_items (
        id INTEGER PRIMARY KEY,
        state_supervision_id INTEGER NOT NULL,
        occurred_at DATETIME,
        title VARCHAR(250) NOT NULL,
        place VARCHAR(250),
        notes TEXT,
        display_order INTEGER NOT NULL DEFAULT 0,
        active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(state_supervision_id) REFERENCES state_supervisions (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervision_timeline_items_state_supervision_id
    ON state_supervision_timeline_items (state_supervision_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervision_timeline_items_list
    ON state_supervision_timeline_items (
        state_supervision_id,
        active,
        display_order
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervision_timeline_items_occurred_at
    ON state_supervision_timeline_items (occurred_at)
    """,
)


@dataclass(frozen=True)
class StateSupervisionTimelineCore3a0SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_state_supervision_timeline_core_3a0_backup_path(
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
        "Nelze přidělit unikátní název zálohy STATE-SUPERVISION-TIMELINE-CORE-3A0."
    )


def needs_state_supervision_timeline_core_3a0_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    return not sqlite_table_exists(path, TABLE_NAME)


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_state_supervision_timeline_core_3a0_schema(path)


def apply_state_supervision_timeline_core_3a0_schema_ddl(db_path: Path) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        for statement in DDL_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_state_supervision_timeline_core_3a0_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> StateSupervisionTimelineCore3a0SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace STATE-SUPERVISION-TIMELINE-CORE-3A0 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return StateSupervisionTimelineCore3a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return StateSupervisionTimelineCore3a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_state_supervision_timeline_core_3a0_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return StateSupervisionTimelineCore3a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_state_supervision_timeline_core_3a0_backup_path(backups_dir)
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
            "STATE-SUPERVISION-TIMELINE-CORE-3A0. Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_state_supervision_timeline_core_3a0_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace STATE-SUPERVISION-TIMELINE-CORE-3A0 selhala. "
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
            "Migrace STATE-SUPERVISION-TIMELINE-CORE-3A0 nedokončila schema. "
            "Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "STATE-SUPERVISION-TIMELINE-CORE-3A0: schema OK, záloha %s",
        backup_path,
    )
    return StateSupervisionTimelineCore3a0SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
