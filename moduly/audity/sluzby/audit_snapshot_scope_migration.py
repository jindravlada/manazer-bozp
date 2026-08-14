"""AUDIT-SNAPSHOT-1b-fix: sloupec is_in_scope + klasifikace existujících snapshotů.

Orphan (result-only) řádky zůstávají v DB s is_in_scope=false — nezobrazují se.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text

from core.backup.constants import BACKUP_EXTENSION
from core.database.session import get_session, reconfigure_database_engine
from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    clear_transition_complete,
    create_verified_pre_migration_backup,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_failed,
    mark_migration_in_progress,
    read_migration_state,
    sqlite_table_exists,
)
from moduly.audity.constants import AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_question_snapshot_service import (
    audit_question_snapshot_service,
    snapshot_key,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import schema_is_present

logger = logging.getLogger(__name__)

TRANSITION_ID = "audit-snapshot-1b-fix"
BACKUP_NAME_PREFIX = "pre_audit_snapshot_scope_fix"
SCOPE_COLUMN = "is_in_scope"


class AuditSnapshotScopeFixError(MigrationGuardError):
    """Klasifikace rozsahu snapshotů selhala — transakce vrácena."""


@dataclass(frozen=True)
class AuditSnapshotScopeFixResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    classified_in_scope: int = 0
    classified_out_of_scope: int = 0
    skipped_reason: str | None = None


def allocate_scope_fix_backup_path(
    backups_dir: Path,
    *,
    when: datetime | None = None,
) -> Path:
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
        "Nelze přidělit unikátní název předmigrační zálohy AUDIT-SNAPSHOT-1b-fix."
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


def scope_column_present(db_path: Path) -> bool:
    if not schema_is_present(db_path):
        return False
    return SCOPE_COLUMN in _table_columns(db_path, "audit_question_snapshots")


def needs_scope_column(db_path: Path) -> bool:
    if not schema_is_present(db_path):
        return False
    return SCOPE_COLUMN not in _table_columns(db_path, "audit_question_snapshots")


def _count_unclassified(db_path: Path) -> int:
    if not scope_column_present(db_path):
        return 0
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM audit_question_snapshots WHERE is_in_scope IS NULL"
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def needs_scope_classification(db_path: Path) -> bool:
    return scope_column_present(db_path) and _count_unclassified(db_path) > 0


def ensure_scope_column(db_path: Path) -> bool:
    """Aditivní ADD COLUMN is_in_scope (nullable). True pokud byl sloupec doplněn."""
    path = Path(db_path)
    if not schema_is_present(path):
        return False
    if scope_column_present(path):
        return False
    connection = sqlite3.connect(str(path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "ALTER TABLE audit_question_snapshots ADD COLUMN is_in_scope BOOLEAN"
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    return True


def _planned_process_ids_for_audit(audit: Audit) -> tuple[str, ...] | None:
    if not audit.program_visit_id:
        return None
    context = audit_program_service.get_visit_audit_context(audit.program_visit_id)
    if context is None:
        return None
    return context.planned_process_ids


def classify_snapshot_rows_for_audit(
    audit: Audit,
    *,
    snapshot_rows: list[AuditQuestionSnapshot],
    methodology_keys: set[tuple[str, str, str]],
) -> tuple[int, int]:
    """
    Nastaví is_in_scope na detached/ORM řádcích.

    Returns:
        (in_scope_count, out_of_scope_count)
    """
    in_scope = 0
    out_of_scope = 0
    for row in snapshot_rows:
        key = snapshot_key(row.process_id, row.section_id, row.assertion_id)
        if key in methodology_keys:
            row.is_in_scope = True
            in_scope += 1
        else:
            # Mimo efektivní sadu — result-only orphan / mimo planned.
            row.is_in_scope = False
            out_of_scope += 1
    return in_scope, out_of_scope


def _verify_all_classified(session) -> None:
    remaining = int(
        session.execute(
            text(
                "SELECT COUNT(*) FROM audit_question_snapshots "
                "WHERE is_in_scope IS NULL"
            )
        ).scalar()
        or 0
    )
    if remaining:
        raise AuditSnapshotScopeFixError(
            f"Po klasifikaci zůstává {remaining} snapshotových řádků "
            "s is_in_scope=NULL."
        )


def prepare_audit_snapshot_scope_fix(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
) -> AuditSnapshotScopeFixResult:
    """
    Zajistí sloupec is_in_scope a klasifikuje existující snapshoty.

    Idempotentní. Při chybě ROLLBACK + mark failed. Bez mazání dat.
    """
    from core.services.storage_service import storage_service

    if workspace_root is None or database_path is None:
        storage_service.ensure_structure()
        workspace_root = workspace_root or storage_service.base
        database_path = database_path or storage_service.database_path

    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if not schema_is_present(database_path):
        return AuditSnapshotScopeFixResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="schema_not_ready",
        )

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        mark_migration_failed(
            workspace_root,
            backup_path=Path(backup) if backup else None,
            transition_id=TRANSITION_ID,
            error="interrupted_scope_fix",
        )
        logger.warning(
            "AUDIT-SNAPSHOT-1b-fix: nedokončená migrace uvolněna. Záloha: %s",
            backup or "(nenalezena)",
        )

    column_missing = needs_scope_column(database_path)
    unclassified = _count_unclassified(database_path) if not column_missing else -1
    # Pokud sloupec chybí, po ADD budou všechny NULL → potřeba klasifikace.
    needs_work = column_missing or unclassified > 0

    if not needs_work:
        if not is_transition_complete(workspace_root, TRANSITION_ID):
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=TRANSITION_ID
            )
        return AuditSnapshotScopeFixResult(
            migrated=False,
            pre_migration_backup_path=None,
            skipped_reason="transition_already_complete",
        )

    if is_transition_complete(workspace_root, TRANSITION_ID) and needs_work:
        logger.warning(
            "AUDIT-SNAPSHOT-1b-fix: stav completed, ale sloupec/klasifikace "
            "neodpovídá — zneplatňuji complete."
        )
        clear_transition_complete(workspace_root, TRANSITION_ID)

    target = allocate_scope_fix_backup_path(backups_dir)
    try:
        backup_path = create_verified_pre_migration_backup(
            target_path=target,
            workspace_root=workspace_root,
            database_path=database_path,
            settings_path=settings_path,
        )
    except PreMigrationBackupError:
        raise
    except Exception as exc:
        raise PreMigrationBackupError(
            "Nepodařilo se vytvořit předmigrační zálohu AUDIT-SNAPSHOT-1b-fix. "
            "Klasifikace nebyla spuštěna."
        ) from exc

    logger.info("AUDIT-SNAPSHOT-1b-fix: záloha %s", backup_path)
    mark_migration_in_progress(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )

    classified_in = 0
    classified_out = 0

    try:
        if column_missing:
            ensure_scope_column(database_path)
            reconfigure_database_engine(force=True)

        reconfigure_database_engine(force=True)
        knowledge_tree = audit_knowledge_service.get_knowledge_tree(ensure=True)

        with get_session() as session:
            try:
                audits = list(
                    session.scalars(
                        select(Audit)
                        .where(
                            Audit.methodology_source
                            == AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                        )
                        .order_by(Audit.id)
                    )
                )
                # Také klasifikuj řádky auditů, které mají snapshoty i bez markeru
                # (defenzivně) — ale primárně snapshotované.
                all_with_snaps = {
                    int(aid)
                    for aid in session.execute(
                        text(
                            "SELECT DISTINCT audit_id FROM audit_question_snapshots"
                        )
                    ).scalars()
                }
                audit_ids = {a.id for a in audits} | all_with_snaps
                audits_by_id = {a.id: a for a in audits}
                for missing_id in sorted(audit_ids - set(audits_by_id)):
                    loaded = session.get(Audit, missing_id)
                    if loaded is not None:
                        audits_by_id[missing_id] = loaded

                for audit_id in sorted(audits_by_id):
                    audit = audits_by_id[audit_id]
                    snaps = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit.id
                            )
                        )
                    )
                    if not snaps:
                        continue
                    # Přeskoč už klasifikované audity (idempotence po částech).
                    if all(row.is_in_scope is not None for row in snaps):
                        classified_in += sum(1 for row in snaps if row.is_in_scope)
                        classified_out += sum(
                            1 for row in snaps if row.is_in_scope is False
                        )
                        continue

                    planned = _planned_process_ids_for_audit(audit)
                    try:
                        methodology = (
                            audit_question_snapshot_service.build_snapshot_for_audit(
                                audit.id,
                                planned_process_ids=planned,
                                ensure=False,
                                knowledge_tree=knowledge_tree,
                            )
                        )
                    except Exception as exc:
                        raise AuditSnapshotScopeFixError(
                            f"Audit {audit.id}: nelze sestavit efektivní sadu "
                            f"pro klasifikaci: {exc}"
                        ) from exc

                    methodology_keys = {
                        snapshot_key(d.process_id, d.section_id, d.assertion_id)
                        for d in methodology
                    }
                    in_c, out_c = classify_snapshot_rows_for_audit(
                        audit,
                        snapshot_rows=snaps,
                        methodology_keys=methodology_keys,
                    )
                    classified_in += in_c
                    classified_out += out_c

                session.flush()
                _verify_all_classified(session)
                session.commit()
            except Exception:
                session.rollback()
                raise
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=backup_path,
            transition_id=TRANSITION_ID,
            error=str(exc),
        )
        logger.error(
            "AUDIT-SNAPSHOT-1b-fix selhala. Záloha: %s. Detail: %s",
            backup_path,
            exc,
        )
        if isinstance(exc, (AuditSnapshotScopeFixError, PreMigrationBackupError)):
            raise
        raise AuditSnapshotScopeFixError(
            f"Klasifikace AUDIT-SNAPSHOT-1b-fix selhala. Záloha: {backup_path}\n"
            f"Detail: {exc}"
        ) from exc

    mark_migration_complete(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )
    logger.info(
        "AUDIT-SNAPSHOT-1b-fix: hotovo. in_scope=%s out_of_scope=%s backup=%s",
        classified_in,
        classified_out,
        backup_path,
    )
    return AuditSnapshotScopeFixResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
        classified_in_scope=classified_in,
        classified_out_of_scope=classified_out,
    )
