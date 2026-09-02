"""STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0: katalog orgánů a pracovišť."""

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

TRANSITION_ID = "state-supervision-authority-catalog-core-8a0"
BACKUP_NAME_PREFIX = "pre_state_supervision_authority_catalog_"
AUTHORITIES_TABLE = "control_authorities"
OFFICES_TABLE = "control_authority_offices"
SUPERVISIONS_TABLE = "state_supervisions"
AUTHORITY_OFFICE_ID_COLUMN = "authority_office_id"

REQUIRED_AUTHORITY_INDEXES = {
    "uq_control_authorities_code",
    "ix_control_authorities_active",
    "ix_control_authorities_display_order",
    "uq_control_authorities_external_key",
}
REQUIRED_OFFICE_INDEXES = {
    "ix_control_authority_offices_authority_id",
    "ix_control_authority_offices_active",
    "ix_control_authority_offices_display_order",
    "uq_control_authority_offices_external_key",
}

DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS control_authorities (
        id INTEGER PRIMARY KEY,
        code VARCHAR(80) NOT NULL,
        name VARCHAR(250) NOT NULL,
        abbreviation VARCHAR(50),
        website VARCHAR(500),
        active BOOLEAN NOT NULL DEFAULT 1,
        display_order INTEGER NOT NULL DEFAULT 0,
        origin VARCHAR(20) NOT NULL DEFAULT 'manual',
        external_key VARCHAR(160),
        source_url VARCHAR(500),
        last_checked_at DATETIME,
        user_edited_at DATETIME,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_control_authorities_code
    ON control_authorities (code)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_control_authorities_active
    ON control_authorities (active)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_control_authorities_display_order
    ON control_authorities (display_order)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_control_authorities_external_key
    ON control_authorities (external_key)
    WHERE external_key IS NOT NULL
    """,
    """
    CREATE TABLE IF NOT EXISTS control_authority_offices (
        id INTEGER PRIMARY KEY,
        authority_id INTEGER NOT NULL,
        name VARCHAR(250) NOT NULL,
        abbreviation VARCHAR(80),
        address VARCHAR(500),
        phone VARCHAR(50),
        email VARCHAR(150),
        website VARCHAR(500),
        territorial_scope TEXT,
        office_kind VARCHAR(40),
        active BOOLEAN NOT NULL DEFAULT 1,
        display_order INTEGER NOT NULL DEFAULT 0,
        origin VARCHAR(20) NOT NULL DEFAULT 'manual',
        external_key VARCHAR(160),
        source_url VARCHAR(500),
        last_checked_at DATETIME,
        user_edited_at DATETIME,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(authority_id) REFERENCES control_authorities (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_control_authority_offices_authority_id
    ON control_authority_offices (authority_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_control_authority_offices_active
    ON control_authority_offices (active)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_control_authority_offices_display_order
    ON control_authority_offices (display_order)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_control_authority_offices_external_key
    ON control_authority_offices (external_key)
    WHERE external_key IS NOT NULL
    """,
)


@dataclass(frozen=True)
class StateSupervisionAuthorityCatalogCore8a0SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_state_supervision_authority_catalog_core_8a0_backup_path(
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
        "STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0."
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


def needs_state_supervision_authority_catalog_core_8a0_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    connection = sqlite3.connect(str(path.resolve()))
    try:
        if not sqlite_table_exists(path, AUTHORITIES_TABLE):
            return True
        if not sqlite_table_exists(path, OFFICES_TABLE):
            return True
        authority_indexes = _table_indexes(connection, AUTHORITIES_TABLE)
        if not REQUIRED_AUTHORITY_INDEXES.issubset(authority_indexes):
            return True
        office_indexes = _table_indexes(connection, OFFICES_TABLE)
        if not REQUIRED_OFFICE_INDEXES.issubset(office_indexes):
            return True
        if sqlite_table_exists(path, SUPERVISIONS_TABLE):
            columns = _table_columns(connection, SUPERVISIONS_TABLE)
            if AUTHORITY_OFFICE_ID_COLUMN not in columns:
                return True
            indexes = _table_indexes(connection, SUPERVISIONS_TABLE)
            if "ix_state_supervisions_authority_office_id" not in indexes:
                return True
        return False
    finally:
        connection.close()


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_state_supervision_authority_catalog_core_8a0_schema(path)


def apply_state_supervision_authority_catalog_core_8a0_schema_ddl(
    db_path: Path,
) -> None:
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        for statement in DDL_STATEMENTS:
            connection.execute(statement)
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if SUPERVISIONS_TABLE in tables:
            columns = _table_columns(connection, SUPERVISIONS_TABLE)
            if AUTHORITY_OFFICE_ID_COLUMN not in columns:
                connection.execute(
                    "ALTER TABLE state_supervisions "
                    "ADD COLUMN authority_office_id INTEGER"
                )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                ix_state_supervisions_authority_office_id
                ON state_supervisions (authority_office_id)
                """
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_state_supervision_authority_catalog_core_8a0_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> StateSupervisionAuthorityCatalogCore8a0SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0 "
            "nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return StateSupervisionAuthorityCatalogCore8a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return StateSupervisionAuthorityCatalogCore8a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_state_supervision_authority_catalog_core_8a0_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return StateSupervisionAuthorityCatalogCore8a0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_state_supervision_authority_catalog_core_8a0_backup_path(
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
            "STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0. Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_state_supervision_authority_catalog_core_8a0_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0 selhala. "
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
            "Migrace STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0 nedokončila "
            "schema. Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info(
        "STATE-SUPERVISION-AUTHORITY-CATALOG-CORE-8A0: schema OK, záloha %s",
        backup_path,
    )
    return StateSupervisionAuthorityCatalogCore8a0SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
