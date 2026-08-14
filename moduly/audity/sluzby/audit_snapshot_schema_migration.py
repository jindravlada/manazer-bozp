"""AUDIT-SNAPSHOT-0: aditivní schema migrace se zálohou a stavem.

Pouze nové tabulky / nullable sloupce. Bez backfille, bez změny dat.
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

TRANSITION_ID = "audit-snapshot-0"
BACKUP_NAME_PREFIX = "pre_audit_snapshot_migration"

AUDIT_SNAPSHOT_TABLE = "audit_question_snapshots"

AUDIT_SNAPSHOT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("methodology_source", "methodology_source VARCHAR(30)"),
    ("questions_frozen_at", "questions_frozen_at DATETIME"),
    ("methodology_generation", "methodology_generation VARCHAR(80)"),
)

CREATE_AUDIT_QUESTION_SNAPSHOTS_SQL = """
CREATE TABLE IF NOT EXISTS audit_question_snapshots (
    id INTEGER NOT NULL PRIMARY KEY,
    audit_id INTEGER NOT NULL,
    process_id VARCHAR(80) DEFAULT '' NOT NULL,
    process_name VARCHAR(250) DEFAULT '' NOT NULL,
    section_id VARCHAR(80) DEFAULT '' NOT NULL,
    section_name VARCHAR(250) DEFAULT '' NOT NULL,
    assertion_id VARCHAR(80) DEFAULT '' NOT NULL,
    assertion_text TEXT DEFAULT '' NOT NULL,
    verification_type VARCHAR(40) DEFAULT '' NOT NULL,
    severity VARCHAR(30) DEFAULT '' NOT NULL,
    question_kind VARCHAR(40) DEFAULT '' NOT NULL,
    display_order INTEGER DEFAULT 0 NOT NULL,
    created_at DATETIME,
    CONSTRAINT uq_audit_question_snapshot_key
        UNIQUE (audit_id, process_id, section_id, assertion_id)
)
"""

CREATE_AUDIT_QUESTION_SNAPSHOTS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_audit_question_snapshots_audit_id
ON audit_question_snapshots (audit_id)
"""


@dataclass(frozen=True)
class AuditSnapshotSchemaResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    skipped_reason: str | None = None


def allocate_audit_snapshot_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
    """Jednoznačný název ``pre_audit_snapshot_migration_YYYYMMDD_HHMMSS``; nepřepisuje."""
    backups_dir = Path(backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    base = f"{BACKUP_NAME_PREFIX}_{stamp}{BACKUP_EXTENSION}"
    candidate = backups_dir / base
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        alt = backups_dir / f"{BACKUP_NAME_PREFIX}_{stamp}_{index}{BACKUP_EXTENSION}"
        if not alt.exists():
            return alt
    raise PreMigrationBackupError(
        "Nelze přidělit unikátní název předmigrační zálohy AUDIT-SNAPSHOT-0."
    )


def _table_columns(db_path: Path, table_name: str) -> set[str]:
    if not Path(db_path).is_file():
        return set()
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    finally:
        conn.close()
    return {str(row[1]) for row in rows}


def needs_audit_snapshot_schema(db_path: Path) -> bool:
    """True, pokud existuje tabulka audits a chybí snapshot infrastruktura."""
    path = Path(db_path)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if not sqlite_table_exists(path, "audits"):
        return False
    if not sqlite_table_exists(path, AUDIT_SNAPSHOT_TABLE):
        return True
    columns = _table_columns(path, "audits")
    for column_name, _sql in AUDIT_SNAPSHOT_COLUMNS:
        if column_name not in columns:
            return True
    return False


def schema_is_present(db_path: Path) -> bool:
    """True, pokud snapshot tabulka i nullable sloupce na audits existují."""
    path = Path(db_path)
    if not path.is_file():
        return False
    if not sqlite_table_exists(path, AUDIT_SNAPSHOT_TABLE):
        return False
    if not sqlite_table_exists(path, "audits"):
        return False
    columns = _table_columns(path, "audits")
    return all(name in columns for name, _ in AUDIT_SNAPSHOT_COLUMNS)


def apply_audit_snapshot_schema_ddl(db_path: Path) -> None:
    """Aditivní DDL v jedné transakci. Při chybě rollback celé transakce."""
    path = Path(db_path)
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(CREATE_AUDIT_QUESTION_SNAPSHOTS_SQL)
        connection.execute(CREATE_AUDIT_QUESTION_SNAPSHOTS_INDEX_SQL)

        existing = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(audits)").fetchall()
        }
        for column_name, column_sql in AUDIT_SNAPSHOT_COLUMNS:
            if column_name in existing:
                continue
            connection.execute(f"ALTER TABLE audits ADD COLUMN {column_sql}")

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def prepare_audit_snapshot_schema(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
) -> AuditSnapshotSchemaResult:
    """
    Spouštěcí příprava AUDIT-SNAPSHOT-0.

    Pořadí:
    1. Odmítnout start při nedokončené migraci (in_progress).
    2. Pokud schema chybí → ověřená záloha → marker → DDL transakce → complete.
    3. Pokud schema už je a transition není complete → označit complete bez zálohy.
    4. Opakovaný start po úspěchu = no-op.
    """
    from core.services.storage_service import storage_service

    if workspace_root is None or database_path is None:
        storage_service.ensure_structure()
        workspace_root = workspace_root or storage_service.base
        database_path = database_path or storage_service.database_path

    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        if schema_is_present(database_path):
            # DDL dopadlo, marker complete nestihl — dokončit bez nové zálohy.
            mark_migration_complete(
                workspace_root,
                backup_path=Path(backup) if backup else None,
                transition_id=TRANSITION_ID,
            )
            return AuditSnapshotSchemaResult(
                migrated=False,
                pre_migration_backup_path=Path(backup) if backup else None,
                skipped_reason="recovered_complete_after_interrupt",
            )
        # Transakce se typicky vrátila — uvolnit in_progress a povolit opakování.
        mark_migration_failed(
            workspace_root,
            backup_path=Path(backup) if backup else None,
            transition_id=TRANSITION_ID,
            error="interrupted_before_complete_schema_incomplete",
        )
        logger.warning(
            "AUDIT-SNAPSHOT-0: nedokončená migrace s neúplným schema; "
            "stav nastaven na failed, bude opakována. Záloha: %s",
            backup or "(nenalezena)",
        )

    if is_transition_complete(workspace_root, TRANSITION_ID):
        if needs_audit_snapshot_schema(database_path):
            # Defenzivně: marker říká hotovo, ale schema chybí → znovu migrovat.
            pass
        else:
            return AuditSnapshotSchemaResult(
                migrated=False,
                pre_migration_backup_path=None,
                skipped_reason="transition_already_complete",
            )

    if not needs_audit_snapshot_schema(database_path):
        if schema_is_present(database_path) and not is_transition_complete(
            workspace_root, TRANSITION_ID
        ):
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=TRANSITION_ID
            )
        return AuditSnapshotSchemaResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_already_present",
        )

    target = allocate_audit_snapshot_backup_path(backups_dir)
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
            "Nepodařilo se vytvořit předmigrační zálohu AUDIT-SNAPSHOT-0. "
            "Migrace nebyla spuštěna."
        ) from exc

    logger.info(
        "AUDIT-SNAPSHOT-0: vytvořena předmigrační záloha: %s",
        backup_path,
    )

    mark_migration_in_progress(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )

    try:
        apply_audit_snapshot_schema_ddl(database_path)
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error=str(exc),
        )
        logger.error(
            "AUDIT-SNAPSHOT-0: migrace selhala, transakce vrácena. "
            "Předmigrační záloha: %s. Detail: %s",
            backup_path,
            exc,
        )
        raise MigrationGuardError(
            "Migrace AUDIT-SNAPSHOT-0 selhala. Databáze nebyla změněna "
            "(rollback transakce). Předmigrační záloha zůstává zachována.\n\n"
            f"Záloha: {backup_path}\n"
            f"Detail: {exc}"
        ) from exc

    if needs_audit_snapshot_schema(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error="schema still incomplete after DDL",
        )
        raise MigrationGuardError(
            "Migrace AUDIT-SNAPSHOT-0 nedokončila schema. "
            f"Předmigrační záloha: {backup_path}"
        )

    mark_migration_complete(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )
    logger.info(
        "AUDIT-SNAPSHOT-0: migrace dokončena. Záloha: %s",
        backup_path,
    )
    return AuditSnapshotSchemaResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
        skipped_reason=None,
    )
