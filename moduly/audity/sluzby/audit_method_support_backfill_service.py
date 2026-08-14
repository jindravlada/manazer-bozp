"""Backfill metodické podpory pro existující snapshotované audity."""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, text

from core.database.session import get_session
from core.database.upgrade_guard import (
    MigrationGuardError,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_complete,
    mark_migration_failed,
    mark_migration_in_progress,
    read_migration_state,
)
from moduly.audity.constants import (
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    METHOD_SUPPORT_PAYLOAD_VERSION,
    METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL,
    METHOD_SUPPORT_SOURCE_UNAVAILABLE,
    METHOD_SUPPORT_STATUS_AVAILABLE,
    METHOD_SUPPORT_STATUS_EMPTY,
    METHOD_SUPPORT_STATUS_UNAVAILABLE,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.modely.audit_question_support_snapshot import (
    AuditQuestionSupportSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_method_support_payload_service import (
    build_section_index_with_process_knowledge,
    build_support_payload_from_section,
    canonical_json_dumps,
    load_process_knowledge_map_from_tree,
    payload_integrity_hash,
    unavailable_payload,
)
from moduly.audity.sluzby.audit_method_support_photo_service import (
    cleanup_staging,
    freeze_reference_photos_in_payload,
    publish_staged_support_photos,
)
from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
    TRANSITION_ID as SCHEMA_TRANSITION_ID,
    schema_is_present as support_schema_present,
)
from moduly.audity.sluzby.audit_method_support_snapshot_service import (
    compute_audit_support_integrity_hash,
)

logger = logging.getLogger(__name__)

BACKFILL_TRANSITION_ID = "audit-method-support-snapshot-1-backfill"


@dataclass(frozen=True)
class MethodSupportBackfillStats:
    audits_processed: int = 0
    supports_available: int = 0
    supports_empty: int = 0
    supports_unavailable: int = 0
    skipped_existing: int = 0


@dataclass(frozen=True)
class MethodSupportBackfillResult:
    migrated: bool
    stats: MethodSupportBackfillStats
    skipped_reason: str | None = None


def _needs_backfill(db_path: Path) -> bool:
    if not support_schema_present(db_path):
        return False
    connection = sqlite3.connect(str(Path(db_path).resolve()))
    try:
        if not _table_exists(connection, "audit_question_snapshots"):
            return False
        # Snapshotované in-scope běžné otázky bez support řádku.
        missing = connection.execute(
            """
            SELECT COUNT(*)
            FROM audit_question_snapshots q
            JOIN audits a ON a.id = q.audit_id
            WHERE a.methodology_source = ?
              AND IFNULL(q.is_in_scope, 1) = 1
              AND IFNULL(q.question_kind, '') != ?
              AND NOT EXISTS (
                SELECT 1 FROM audit_question_support_snapshots s
                WHERE s.audit_question_snapshot_id = q.id
              )
            """,
            (AUDIT_METHODOLOGY_SOURCE_SNAPSHOT, AUDIT_QUESTION_KIND_EXTRAORDINARY),
        ).fetchone()
        return int(missing[0] or 0) > 0
    finally:
        connection.close()


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def prepare_method_support_backfill(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
) -> MethodSupportBackfillResult:
    workspace_root = Path(workspace_root)
    database_path = Path(database_path)

    if not support_schema_present(database_path):
        return MethodSupportBackfillResult(
            migrated=False,
            stats=MethodSupportBackfillStats(),
            skipped_reason="schema_missing",
        )

    if is_migration_in_progress(workspace_root, BACKFILL_TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        raise MigrationGuardError(
            "Předchozí backfill AUDIT-METHOD-SUPPORT-SNAPSHOT-1 nebyl dokončen.\n"
            f"Stav: {backup or '(viz migration_state)'}"
        )

    if is_transition_complete(workspace_root, BACKFILL_TRANSITION_ID) and not _needs_backfill(
        database_path
    ):
        return MethodSupportBackfillResult(
            migrated=False,
            stats=MethodSupportBackfillStats(),
            skipped_reason="already_complete",
        )

    if not _needs_backfill(database_path):
        mark_migration_complete(
            workspace_root,
            backup_path=None,
            transition_id=BACKFILL_TRANSITION_ID,
        )
        return MethodSupportBackfillResult(
            migrated=False,
            stats=MethodSupportBackfillStats(),
            skipped_reason="nothing_to_do",
        )

    # Záloha už vznikla při schema migraci; backfill vyžaduje dokončené schema.
    if not is_transition_complete(workspace_root, SCHEMA_TRANSITION_ID):
        raise MigrationGuardError(
            "Nelze spustit backfill metodické podpory — schema migrace "
            "AUDIT-METHOD-SUPPORT-SNAPSHOT-1 není dokončená."
        )

    mark_migration_in_progress(
        workspace_root,
        backup_path=None,
        transition_id=BACKFILL_TRANSITION_ID,
    )
    try:
        stats = run_method_support_backfill()
    except Exception as exc:
        mark_migration_failed(
            workspace_root,
            backup_path=None,
            error=str(exc),
            transition_id=BACKFILL_TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Backfill AUDIT-METHOD-SUPPORT-SNAPSHOT-1 selhal. "
            "Obnovte data ze zálohy pre_audit_method_support_snapshot_*."
        ) from exc

    if _needs_backfill(database_path):
        mark_migration_failed(
            workspace_root,
            backup_path=None,
            error="backfill_incomplete",
            transition_id=BACKFILL_TRANSITION_ID,
        )
        raise MigrationGuardError(
            "Backfill AUDIT-METHOD-SUPPORT-SNAPSHOT-1 nedokončil všechna data."
        )

    mark_migration_complete(
        workspace_root,
        backup_path=None,
        transition_id=BACKFILL_TRANSITION_ID,
    )
    logger.info(
        "AUDIT-METHOD-SUPPORT-SNAPSHOT-1 backfill OK: audits=%s available=%s "
        "empty=%s unavailable=%s skipped=%s",
        stats.audits_processed,
        stats.supports_available,
        stats.supports_empty,
        stats.supports_unavailable,
        stats.skipped_existing,
    )
    return MethodSupportBackfillResult(migrated=True, stats=stats)


def run_method_support_backfill() -> MethodSupportBackfillStats:
    """Jedno načtení metodiky + atomický zápis všech chybějících support řádků."""
    # Jediné načtení živé metodiky pro celý backfill.
    knowledge_tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
    process_map = load_process_knowledge_map_from_tree(knowledge_tree)
    section_index = build_section_index_with_process_knowledge(
        knowledge_tree,
        process_knowledge_by_id=process_map,
    )

    staging_root = Path(tempfile.mkdtemp(prefix="method-support-backfill-"))
    staged_files: list[Path] = []
    stats = MethodSupportBackfillStats()
    available = empty = unavailable = skipped = audits_processed = 0

    try:
        with get_session() as session:
            try:
                existing_ids = {
                    int(row[0])
                    for row in session.execute(
                        text(
                            "SELECT audit_question_snapshot_id "
                            "FROM audit_question_support_snapshots"
                        )
                    )
                }
                audits = list(
                    session.scalars(
                        select(Audit).where(
                            Audit.methodology_source
                            == AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                        )
                    )
                )
                payload_cache: dict[tuple[str, str], tuple[str, str, str]] = {}
                created_by_audit: dict[int, list[AuditQuestionSupportSnapshot]] = {}

                for audit in audits:
                    questions = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == int(audit.id)
                            )
                        )
                    )
                    created_rows: list[AuditQuestionSupportSnapshot] = []
                    for question in questions:
                        if question.is_in_scope is False:
                            continue
                        kind = interpret_question_kind(question.question_kind)
                        if kind == AUDIT_QUESTION_KIND_EXTRAORDINARY:
                            continue
                        qid = int(question.id)
                        if qid in existing_ids:
                            skipped += 1
                            continue
                        key = (str(question.process_id), str(question.section_id))
                        if key not in payload_cache:
                            if key not in section_index:
                                payload = unavailable_payload()
                                status = METHOD_SUPPORT_STATUS_UNAVAILABLE
                                source = METHOD_SUPPORT_SOURCE_UNAVAILABLE
                            else:
                                section, process_knowledge = section_index[key]
                                payload, status = build_support_payload_from_section(
                                    section=section,
                                    process_knowledge=process_knowledge,
                                )
                                source = METHOD_SUPPORT_SOURCE_LIVE_AT_LEGACY_BACKFILL
                            payload, more = freeze_reference_photos_in_payload(
                                payload, staging_dir=staging_root
                            )
                            staged_files.extend(more)
                            canonical = canonical_json_dumps(payload)
                            payload_cache[key] = (canonical, status, source)
                        canonical, status, source = payload_cache[key]
                        row = AuditQuestionSupportSnapshot(
                            audit_id=int(audit.id),
                            audit_question_snapshot_id=qid,
                            payload_version=METHOD_SUPPORT_PAYLOAD_VERSION,
                            support_payload_json=canonical,
                            source=source,
                            status=status,
                            integrity_hash=payload_integrity_hash(canonical),
                            created_at=datetime.now(),
                        )
                        session.add(row)
                        created_rows.append(row)
                        if status == METHOD_SUPPORT_STATUS_UNAVAILABLE:
                            unavailable += 1
                        elif status == METHOD_SUPPORT_STATUS_EMPTY:
                            empty += 1
                        else:
                            available += 1

                    if created_rows:
                        session.flush()
                        # Manifest: existující + nové
                        all_support = list(
                            session.scalars(
                                select(AuditQuestionSupportSnapshot).where(
                                    AuditQuestionSupportSnapshot.audit_id
                                    == int(audit.id)
                                )
                            )
                        )
                        audit.support_snapshot_count = len(all_support)
                        audit.support_integrity_hash = (
                            compute_audit_support_integrity_hash(all_support)
                        )
                        created_by_audit[int(audit.id)] = created_rows
                        audits_processed += 1

                publish_staged_support_photos(staged_files, staging_root)
                session.commit()
            except Exception:
                session.rollback()
                raise
    finally:
        cleanup_staging(staging_root)

    return MethodSupportBackfillStats(
        audits_processed=audits_processed,
        supports_available=available,
        supports_empty=empty,
        supports_unavailable=unavailable,
        skipped_existing=skipped,
    )
