"""AUDIT-SNAPSHOT-URGENT-1: DB-only integrita snapshotu + count/hash manifest.

Zmrazený snapshot se neporovnává s živou JSON metodikou.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

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
)
from core.shared.constants import ENTITY_AUDITY
from core.shared.modely.control_result import ControlResult
from moduly.audity.constants import AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.sluzby.audit_question_snapshot_service import (
    AuditQuestionSnapshotDraft,
    snapshot_key,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import schema_is_present

logger = logging.getLogger(__name__)

TRANSITION_ID = "audit-snapshot-integrity-seal"
BACKUP_NAME_PREFIX = "pre_audit_snapshot_integrity_fix"

INTEGRITY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("snapshot_question_count", "snapshot_question_count INTEGER"),
    ("snapshot_integrity_hash", "snapshot_integrity_hash VARCHAR(64)"),
)


class AuditSnapshotIntegrityError(MigrationGuardError):
    """Integrita snapshotu selhala — bez přepisu dat."""


@dataclass(frozen=True)
class AuditSnapshotIntegritySealResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    sealed_audits: int = 0
    skipped_reason: str | None = None


def allocate_integrity_seal_backup_path(
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
        "Nelze přidělit unikátní název předmigrační zálohy "
        "AUDIT-SNAPSHOT-URGENT-1."
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


def integrity_columns_present(db_path: Path) -> bool:
    if not Path(db_path).is_file():
        return False
    columns = _table_columns(db_path, "audits")
    return all(name in columns for name, _ddl in INTEGRITY_COLUMNS)


def needs_integrity_columns(db_path: Path) -> bool:
    if not schema_is_present(db_path):
        return False
    path = Path(db_path)
    if not path.is_file():
        return False
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "audits" not in tables:
            return False
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(audits)")}
    finally:
        connection.close()
    return any(name not in columns for name, _ddl in INTEGRITY_COLUMNS)


def ensure_integrity_columns(db_path: Path) -> bool:
    """Aditivní ADD COLUMN. True pokud byl alespoň jeden sloupec doplněn."""
    path = Path(db_path)
    if not path.is_file():
        return False
    connection = sqlite3.connect(str(path.resolve()))
    added = False
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "audits" not in tables:
            return False
        existing = {str(row[1]) for row in connection.execute("PRAGMA table_info(audits)")}
        for name, ddl in INTEGRITY_COLUMNS:
            if name in existing:
                continue
            connection.execute(f"ALTER TABLE audits ADD COLUMN {ddl}")
            added = True
        connection.commit()
    finally:
        connection.close()
    return added


def snapshot_rows_as_drafts(
    audit_id: int,
    snapshot_rows: Sequence[AuditQuestionSnapshot],
) -> list[AuditQuestionSnapshotDraft]:
    return [
        AuditQuestionSnapshotDraft(
            audit_id=audit_id,
            process_id=row.process_id,
            process_name=row.process_name,
            section_id=row.section_id,
            section_name=row.section_name,
            assertion_id=row.assertion_id,
            assertion_text=row.assertion_text,
            verification_type=row.verification_type,
            severity=row.severity,
            question_kind=row.question_kind,
            display_order=row.display_order,
        )
        for row in snapshot_rows
    ]


def match_result_to_snapshot_drafts(
    result: ControlResult,
    drafts: Sequence[AuditQuestionSnapshotDraft],
) -> AuditQuestionSnapshotDraft | None:
    id_key = snapshot_key(
        result.source_area_id,
        result.source_section_id,
        result.source_control_point_id,
    )
    by_key = {
        snapshot_key(d.process_id, d.section_id, d.assertion_id): d for d in drafts
    }
    if id_key[2] and id_key in by_key:
        return by_key[id_key]

    label_area = str(result.source_area_label or "").strip()
    label_section = str(result.source_section_label or "").strip()
    cp = str(result.source_control_point_id or "").strip()
    for draft in drafts:
        if draft.assertion_id != cp:
            continue
        if (
            draft.process_name.strip() == label_area
            and draft.section_name.strip() == label_section
        ):
            return draft

    process_id = str(result.source_area_id or "").strip() or f"orphan_process_{result.id}"
    section_id = (
        str(result.source_section_id or "").strip() or f"orphan_section_{result.id}"
    )
    assertion_id = cp or f"orphan_cr_{result.id}"
    for candidate_assertion in (
        assertion_id,
        f"{cp}__cr{result.id}" if cp else f"orphan_cr_{result.id}",
        f"orphan_cr_{result.id}",
    ):
        key = snapshot_key(process_id, section_id, candidate_assertion)
        if key in by_key:
            return by_key[key]
    return None


def compute_snapshot_integrity_hash(
    snapshot_rows: Sequence[AuditQuestionSnapshot],
) -> str:
    """Stabilní hash pouze z uložených snapshotových řádků (bez live JSON / CR)."""
    lines: list[str] = []
    ordered = sorted(
        snapshot_rows,
        key=lambda row: (
            str(row.process_id or ""),
            str(row.section_id or ""),
            str(row.assertion_id or ""),
            int(getattr(row, "id", 0) or 0),
        ),
    )
    for row in ordered:
        if row.is_in_scope is True:
            scope = "1"
        elif row.is_in_scope is False:
            scope = "0"
        else:
            scope = ""
        lines.append(
            "|".join(
                [
                    str(row.process_id or ""),
                    str(row.section_id or ""),
                    str(row.assertion_id or ""),
                    str(row.assertion_text or ""),
                    str(row.verification_type or ""),
                    str(row.question_kind or ""),
                    scope,
                    str(int(row.display_order or 0)),
                ]
            )
        )
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def diagnose_frozen_snapshot_db_only(
    audit: Audit,
    *,
    snapshot_rows: Sequence[AuditQuestionSnapshot],
    control_results: Sequence[ControlResult],
    require_manifest: bool = True,
) -> list[str]:
    """Přesné důvody nekonzistence — bez porovnání s živou metodikou."""
    reasons: list[str] = []
    source = str(audit.methodology_source or "").strip()
    generation = str(audit.methodology_generation or "").strip()

    if source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT:
        reasons.append(f"chybí methodology marker (source={source or 'NULL'})")
    if audit.questions_frozen_at is None:
        reasons.append("chybí questions_frozen_at")
    if not generation:
        reasons.append("chybí methodology_generation")

    if not snapshot_rows:
        reasons.append("chybí snapshotové řádky pro zmrazený audit")
        return reasons

    keys: list[tuple[str, str, str]] = []
    for row in snapshot_rows:
        if getattr(row, "audit_id", None) not in (None, audit.id):
            reasons.append(
                f"snapshot id={getattr(row, 'id', '?')} má cizí audit_id="
                f"{getattr(row, 'audit_id', None)}"
            )
        if row.is_in_scope is None:
            reasons.append(
                f"is_in_scope IS NULL (snapshot id={getattr(row, 'id', '?')})"
            )
        if not str(row.process_id or "").strip():
            reasons.append(
                f"chybí process_id (snapshot id={getattr(row, 'id', '?')})"
            )
        if not str(row.section_id or "").strip():
            reasons.append(
                f"chybí section_id (snapshot id={getattr(row, 'id', '?')})"
            )
        if not str(row.assertion_id or "").strip():
            reasons.append(
                f"chybí assertion_id (snapshot id={getattr(row, 'id', '?')})"
            )
        if not str(row.assertion_text or "").strip():
            reasons.append(
                f"chybí assertion_text (snapshot id={getattr(row, 'id', '?')})"
            )
        keys.append(
            snapshot_key(row.process_id, row.section_id, row.assertion_id)
        )
    if len(keys) != len(set(keys)):
        reasons.append("porušen unikátní klíč snapshotu (duplicitní process/section/assertion)")

    drafts = snapshot_rows_as_drafts(audit.id, snapshot_rows)
    for result in control_results:
        if match_result_to_snapshot_drafts(result, drafts) is None:
            reasons.append(
                f"chybí snapshotový řádek pro control_result id={result.id}"
            )

    stored_count = getattr(audit, "snapshot_question_count", None)
    stored_hash = str(getattr(audit, "snapshot_integrity_hash", None) or "").strip()
    if require_manifest:
        if stored_count is None:
            reasons.append("chybí snapshot_question_count (manifest)")
        if not stored_hash:
            reasons.append("chybí snapshot_integrity_hash (manifest)")
    if stored_count is not None and int(stored_count) != len(snapshot_rows):
        reasons.append(
            f"nesoulad počtu snapshotů: manifest={int(stored_count)}, "
            f"db={len(snapshot_rows)}"
        )
    if stored_hash:
        actual_hash = compute_snapshot_integrity_hash(snapshot_rows)
        if actual_hash != stored_hash:
            reasons.append("nesoulad snapshot_integrity_hash vůči snapshotovým řádkům")

    return reasons


def apply_snapshot_integrity_manifest(
    audit: Audit,
    snapshot_rows: Sequence[AuditQuestionSnapshot],
) -> None:
    """Zapíše count/hash na audit (volající drží transakci)."""
    audit.snapshot_question_count = len(snapshot_rows)
    audit.snapshot_integrity_hash = compute_snapshot_integrity_hash(snapshot_rows)


def audit_needs_integrity_seal(audit: Audit) -> bool:
    source = str(audit.methodology_source or "").strip()
    if source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT:
        return False
    if audit.questions_frozen_at is None:
        return False
    if not str(audit.methodology_generation or "").strip():
        return False
    if getattr(audit, "snapshot_question_count", None) is None:
        return True
    if not str(getattr(audit, "snapshot_integrity_hash", None) or "").strip():
        return True
    return False


def prepare_audit_snapshot_integrity_seal(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
) -> AuditSnapshotIntegritySealResult:
    """Jednorázové zapečetění existujících snapshotů (count/hash) bez live JSON."""
    from core.services.storage_service import storage_service

    if workspace_root is None or database_path is None:
        storage_service.ensure_structure()
        workspace_root = workspace_root or storage_service.base
        database_path = database_path or storage_service.database_path

    workspace_root = Path(workspace_root)
    database_path = Path(database_path)
    backups_dir = workspace_root / "zalohy"

    if not schema_is_present(database_path):
        return AuditSnapshotIntegritySealResult(
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
            error="interrupted_integrity_seal",
        )
        logger.warning(
            "AUDIT-SNAPSHOT-URGENT-1: nedokončené zapečetění uvolněno. Záloha: %s",
            backup or "(nenalezena)",
        )

    columns_missing = needs_integrity_columns(database_path)
    if columns_missing:
        ensure_integrity_columns(database_path)
        reconfigure_database_engine(force=True)

    reconfigure_database_engine(force=True)

    with get_session() as session:
        audits = list(session.scalars(select(Audit).order_by(Audit.id)))
        to_seal: list[tuple[Audit, list[AuditQuestionSnapshot], list[ControlResult]]] = []
        for audit in audits:
            if not audit_needs_integrity_seal(audit):
                continue
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            results = list(
                session.scalars(
                    select(ControlResult)
                    .where(
                        ControlResult.entity_type == ENTITY_AUDITY,
                        ControlResult.entity_id == audit.id,
                    )
                    .order_by(ControlResult.id)
                )
            )
            reasons = diagnose_frozen_snapshot_db_only(
                audit,
                snapshot_rows=snaps,
                control_results=results,
                require_manifest=False,
            )
            if reasons:
                detail = "; ".join(reasons)
                raise AuditSnapshotIntegrityError(
                    "AUDIT-SNAPSHOT-URGENT-1: nelze zapečetit snapshot — "
                    f"audit id={audit.id}: {detail}. "
                    "Žádná data nebyla přepsána. Obnovte zálohu nebo opravte data ručně."
                )
            to_seal.append((audit, snaps, results))
            for row in snaps:
                session.expunge(row)
            for row in results:
                session.expunge(row)
            session.expunge(audit)

    if not to_seal and not columns_missing:
        if not is_transition_complete(workspace_root, TRANSITION_ID):
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=TRANSITION_ID
            )
        return AuditSnapshotIntegritySealResult(
            migrated=False,
            pre_migration_backup_path=None,
            sealed_audits=0,
            skipped_reason="transition_already_complete",
        )

    if not to_seal:
        # Sloupce doplněny, ale není co pečetit (např. čistá instalace).
        if not is_transition_complete(workspace_root, TRANSITION_ID):
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=TRANSITION_ID
            )
        return AuditSnapshotIntegritySealResult(
            migrated=columns_missing,
            pre_migration_backup_path=None,
            sealed_audits=0,
            skipped_reason="no_snapshots_to_seal",
        )

    if is_transition_complete(workspace_root, TRANSITION_ID):
        logger.warning(
            "AUDIT-SNAPSHOT-URGENT-1: stav completed, ale chybí manifest — "
            "zneplatňuji complete a pečetím."
        )
        clear_transition_complete(workspace_root, TRANSITION_ID)

    target = allocate_integrity_seal_backup_path(backups_dir)
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
            "Nepodařilo se vytvořit předmigrační zálohu AUDIT-SNAPSHOT-URGENT-1. "
            "Zapečetění nebylo spuštěno."
        ) from exc

    logger.info("AUDIT-SNAPSHOT-URGENT-1: záloha %s", backup_path)
    mark_migration_in_progress(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )

    sealed = 0
    try:
        reconfigure_database_engine(force=True)
        with get_session() as session:
            try:
                for detached, _snaps, _results in to_seal:
                    audit = session.get(Audit, detached.id)
                    if audit is None:
                        raise AuditSnapshotIntegrityError(
                            f"Audit {detached.id} zmizel během zapečetění."
                        )
                    snaps = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit.id
                            )
                        )
                    )
                    results = list(
                        session.scalars(
                            select(ControlResult)
                            .where(
                                ControlResult.entity_type == ENTITY_AUDITY,
                                ControlResult.entity_id == audit.id,
                            )
                            .order_by(ControlResult.id)
                        )
                    )
                    reasons = diagnose_frozen_snapshot_db_only(
                        audit,
                        snapshot_rows=snaps,
                        control_results=results,
                        require_manifest=False,
                    )
                    if reasons:
                        raise AuditSnapshotIntegrityError(
                            f"Audit id={audit.id}: {'; '.join(reasons)}"
                        )
                    apply_snapshot_integrity_manifest(audit, snaps)
                    sealed += 1
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
            "AUDIT-SNAPSHOT-URGENT-1 selhalo. Záloha: %s. Detail: %s",
            backup_path,
            exc,
        )
        if isinstance(exc, (AuditSnapshotIntegrityError, PreMigrationBackupError)):
            raise
        raise AuditSnapshotIntegrityError(
            f"Zapečetění AUDIT-SNAPSHOT-URGENT-1 selhalo. Záloha: {backup_path}\n"
            f"Detail: {exc}"
        ) from exc

    mark_migration_complete(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )
    logger.info(
        "AUDIT-SNAPSHOT-URGENT-1: zapečetěno auditů=%s, záloha=%s",
        sealed,
        backup_path,
    )
    return AuditSnapshotIntegritySealResult(
        migrated=True,
        pre_migration_backup_path=backup_path,
        sealed_audits=sealed,
    )
