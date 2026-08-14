"""EXTERNAL-AUDIT-EA-0: aditivní schema externích auditů + ověřená záloha."""

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

TRANSITION_ID = "external-audit-ea-0"
BACKUP_NAME_PREFIX = "pre_external_audit_ea_0"

REQUIRED_TABLES: tuple[str, ...] = (
    "external_audits",
    "external_audit_visits",
    "external_audit_participants",
    "external_audit_visit_participants",
    "external_audit_findings",
    "external_audit_finding_task_links",
)

DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS external_audits (
        id INTEGER PRIMARY KEY,
        audit_type VARCHAR(40) NOT NULL DEFAULT 'surveillance',
        status VARCHAR(40) NOT NULL DEFAULT 'planned',
        remind_from DATE,
        organization_ico VARCHAR(20) NOT NULL DEFAULT '',
        organization_name VARCHAR(250) NOT NULL DEFAULT '',
        organization_address VARCHAR(500) NOT NULL DEFAULT '',
        organization_snapshot_json TEXT,
        note TEXT,
        created_at DATETIME,
        updated_at DATETIME
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audits_status
    ON external_audits (status)
    """,
    """
    CREATE TABLE IF NOT EXISTS external_audit_visits (
        id INTEGER PRIMARY KEY,
        external_audit_id INTEGER NOT NULL,
        visit_date DATE NOT NULL,
        time_from VARCHAR(8),
        time_to VARCHAR(8),
        workplace_id INTEGER NOT NULL,
        workplace_name_snapshot VARCHAR(150) NOT NULL DEFAULT '',
        workplace_address_snapshot VARCHAR(250) NOT NULL DEFAULT '',
        display_order INTEGER NOT NULL DEFAULT 0,
        note TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(external_audit_id) REFERENCES external_audits (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visits_audit_id
    ON external_audit_visits (external_audit_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visits_visit_date
    ON external_audit_visits (visit_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visits_audit_date
    ON external_audit_visits (external_audit_id, visit_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visits_workplace_id
    ON external_audit_visits (workplace_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS external_audit_participants (
        id INTEGER PRIMARY KEY,
        external_audit_id INTEGER NOT NULL,
        role VARCHAR(40) NOT NULL,
        source_type VARCHAR(40) NOT NULL,
        source_id INTEGER NOT NULL,
        display_name_snapshot VARCHAR(250) NOT NULL DEFAULT '',
        display_order INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(external_audit_id) REFERENCES external_audits (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_participants_audit_id
    ON external_audit_participants (external_audit_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_participants_role
    ON external_audit_participants (role)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_participants_audit_role
    ON external_audit_participants (external_audit_id, role)
    """,
    """
    CREATE TABLE IF NOT EXISTS external_audit_visit_participants (
        id INTEGER PRIMARY KEY,
        visit_id INTEGER NOT NULL,
        participant_id INTEGER NOT NULL,
        created_at DATETIME,
        CONSTRAINT uq_external_audit_visit_participant
            UNIQUE (visit_id, participant_id),
        FOREIGN KEY(visit_id) REFERENCES external_audit_visits (id),
        FOREIGN KEY(participant_id) REFERENCES external_audit_participants (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visit_participants_visit_id
    ON external_audit_visit_participants (visit_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_visit_participants_participant_id
    ON external_audit_visit_participants (participant_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS external_audit_findings (
        id INTEGER PRIMARY KEY,
        external_audit_id INTEGER NOT NULL,
        finding_type VARCHAR(40) NOT NULL DEFAULT 'nonconformity',
        description TEXT NOT NULL DEFAULT '',
        status VARCHAR(40) NOT NULL DEFAULT 'open',
        due_date DATE,
        resolution_text TEXT,
        resolved_at DATETIME,
        display_order INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(external_audit_id) REFERENCES external_audits (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_findings_audit_id
    ON external_audit_findings (external_audit_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_findings_finding_type
    ON external_audit_findings (finding_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_findings_status
    ON external_audit_findings (status)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_findings_due_date
    ON external_audit_findings (due_date)
    """,
    """
    CREATE TABLE IF NOT EXISTS external_audit_finding_task_links (
        id INTEGER PRIMARY KEY,
        finding_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        created_at DATETIME,
        CONSTRAINT uq_external_audit_finding_task
            UNIQUE (finding_id, task_id),
        FOREIGN KEY(finding_id) REFERENCES external_audit_findings (id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_finding_task_links_finding_id
    ON external_audit_finding_task_links (finding_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_external_audit_finding_task_links_task_id
    ON external_audit_finding_task_links (task_id)
    """,
)


@dataclass(frozen=True)
class ExternalAuditEa0SchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_external_audit_ea_0_backup_path(
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
        "Nelze přidělit unikátní název zálohy EXTERNAL-AUDIT-EA-0."
    )


def needs_external_audit_ea_0_schema(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    for table in REQUIRED_TABLES:
        if not sqlite_table_exists(path, table):
            return True
    return False


def schema_is_present(db_path: Path) -> bool:
    path = Path(db_path)
    if not path.is_file():
        return False
    return not needs_external_audit_ea_0_schema(path)


def apply_external_audit_ea_0_schema_ddl(db_path: Path) -> None:
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


def prepare_external_audit_ea_0_schema(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> ExternalAuditEa0SchemaResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí migrace EXTERNAL-AUDIT-EA-0 nebyla dokončena.\n"
            f"Záloha: {backup or '(nenalezena)'}"
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and schema_is_present(
        database_path
    ):
        return ExternalAuditEa0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="already_complete",
        )

    if not database_path.is_file():
        return ExternalAuditEa0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="no_database",
        )

    if not needs_external_audit_ea_0_schema(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=TRANSITION_ID,
        )
        return ExternalAuditEa0SchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_present",
        )

    target = allocate_external_audit_ea_0_backup_path(backups_dir)
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
            "Nepodařilo se vytvořit zálohu před migrací EXTERNAL-AUDIT-EA-0. "
            "Migrace nebyla spuštěna."
        ) from exc

    mark_migration_in_progress(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    try:
        apply_external_audit_ea_0_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error=str(exc),
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace EXTERNAL-AUDIT-EA-0 selhala. Obnovte data ze zálohy."
        ) from exc

    if not schema_is_present(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            error="schema_not_present_after_ddl",
            transition_id=TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Migrace EXTERNAL-AUDIT-EA-0 nedokončila schema. Obnovte data ze zálohy."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=backup_path,
        transition_id=TRANSITION_ID,
    )
    logger.info("EXTERNAL-AUDIT-EA-0: schema OK, záloha %s", backup_path)
    return ExternalAuditEa0SchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
    )
