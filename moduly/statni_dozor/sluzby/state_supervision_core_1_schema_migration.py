"""STATE-SUPERVISION-CORE-1: aditivní schema státního dozoru + ověřená záloha."""

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

TRANSITION_ID = "state-supervision-core-1"
BACKUP_NAME_PREFIX = "pre_state_supervision_core"
TABLE_NAME = "state_supervisions"

DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS state_supervisions (
        id INTEGER PRIMARY KEY,
        status VARCHAR(40) NOT NULL DEFAULT 'announced',
        authority_ico VARCHAR(20),
        authority_name VARCHAR(250) NOT NULL,
        authority_address VARCHAR(500),
        workplace_id INTEGER,
        workplace_name_snapshot VARCHAR(150) NOT NULL DEFAULT '',
        workplace_address_snapshot VARCHAR(250) NOT NULL DEFAULT '',
        notification_method VARCHAR(40),
        announced_at DATETIME,
        notification_note TEXT,
        trade_union_notified_at DATETIME,
        management_notified_at DATETIME,
        planned_start_at DATETIME,
        planned_start_place VARCHAR(250),
        planned_control_place VARCHAR(250),
        started_at DATETIME,
        ended_at DATETIME,
        closed_at DATETIME,
        file_number VARCHAR(100),
        subject TEXT,
        initial_information TEXT,
        preparation_note TEXT,
        power_of_attorney_required BOOLEAN NOT NULL DEFAULT 0,
        power_of_attorney_note TEXT,
        result TEXT,
        final_summary TEXT,
        protocol_number VARCHAR(100),
        protocol_received_at DATETIME,
        objections_due_at DATETIME,
        objections_submitted_at DATETIME,
        objections_note TEXT,
        completion_evidence_sent_at DATETIME,
        authority_confirmation_at DATETIME,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_status
    ON state_supervisions (status)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_authority_name
    ON state_supervisions (authority_name)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_workplace_id
    ON state_supervisions (workplace_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_started_at
    ON state_supervisions (started_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_ended_at
    ON state_supervisions (ended_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_state_supervisions_closed_at
    ON state_supervisions (closed_at)
    """,
)


@dataclass(frozen=True)
class StateSupervisionCore1SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_state_supervision_core_1_backup_path(
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
        "Nelze přidělit unikátní název zálohy STATE-SUPERVISION-CORE-1."
    )


def needs_state_supervision_core_1_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    return not sqlite_table_exists(path, TABLE_NAME)


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_state_supervision_core_1_schema(path)


def apply_state_supervision_core_1_schema_ddl(db_path: Path) -> None:
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


def prepare_state_supervision_core_1_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> StateSupervisionCore1SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace STATE-SUPERVISION-CORE-1 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return StateSupervisionCore1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return StateSupervisionCore1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_state_supervision_core_1_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return StateSupervisionCore1SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_state_supervision_core_1_backup_path(backups_dir)
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
            "Nepodařilo se vytvořit zálohu před migrací STATE-SUPERVISION-CORE-1. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_state_supervision_core_1_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace STATE-SUPERVISION-CORE-1 selhala. Obnovte data ze zálohy."
        ) from exc

    if not schema_is_present(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error="schema_not_present_after_ddl",
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace STATE-SUPERVISION-CORE-1 nedokončila schema. "
            "Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info("STATE-SUPERVISION-CORE-1: schema OK, záloha %s", backup_path)
    return StateSupervisionCore1SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
