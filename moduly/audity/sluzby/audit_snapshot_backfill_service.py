"""AUDIT-SNAPSHOT-1a: atomický backfill snapshotů existujících auditů."""

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
from core.shared.constants import ENTITY_AUDITY
from core.shared.modely.control_result import ControlResult
from moduly.audity.constants import (
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    AUDIT_QUESTION_KIND_LEGACY,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_program import AuditProgramVisit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_question_snapshot_service import (
    AuditQuestionSnapshotDraft,
    audit_question_snapshot_service,
    snapshot_key,
)
from moduly.audity.sluzby.audit_snapshot_integrity_service import (
    apply_snapshot_integrity_manifest,
    diagnose_frozen_snapshot_db_only,
    match_result_to_snapshot_drafts,
    snapshot_rows_as_drafts,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import schema_is_present

logger = logging.getLogger(__name__)

TRANSITION_ID = "audit-snapshot-1a"
BACKUP_NAME_PREFIX = "pre_audit_snapshot_backfill"


@dataclass(frozen=True)
class AuditBackfillInventoryItem:
    audit_id: int
    status: str
    workplace_id: int | None
    program_id: int | None
    program_visit_id: int | None
    control_results_count: int
    planned_process_count: int
    methodology_question_count: int
    orphan_result_count: int
    already_complete: bool


@dataclass(frozen=True)
class AuditBackfillReportItem:
    audit_id: int
    status: str
    snapshot_question_count: int
    questions_with_result: int
    orphan_count: int
    validation_ok: bool
    skipped: bool
    detail: str = ""


@dataclass(frozen=True)
class AuditSnapshotBackfillResult:
    migrated: bool
    pre_migration_backup_path: Path | None
    processed_audits: int
    skipped_audits: int
    visits_without_audit: int
    report: tuple[AuditBackfillReportItem, ...]
    skipped_reason: str | None = None


class AuditSnapshotBackfillError(MigrationGuardError):
    """Backfill selhal — transakce vrácena."""


def allocate_backfill_backup_path(
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
        "Nelze přidělit unikátní název předmigrační zálohy AUDIT-SNAPSHOT-1a."
    )


def _planned_process_ids_for_audit(audit: Audit) -> tuple[str, ...] | None:
    if not audit.program_visit_id:
        return None
    context = audit_program_service.get_visit_audit_context(audit.program_visit_id)
    if context is None:
        return None
    return context.planned_process_ids


def _snapshot_rows_as_drafts(
    audit_id: int,
    snapshot_rows: list[AuditQuestionSnapshot],
) -> list[AuditQuestionSnapshotDraft]:
    return snapshot_rows_as_drafts(audit_id, snapshot_rows)


def _is_audit_snapshot_complete(
    audit: Audit,
    *,
    snapshot_rows: list[AuditQuestionSnapshot],
    control_results: list[ControlResult],
    methodology_drafts: list[AuditQuestionSnapshotDraft] | None = None,
) -> bool:
    """DB-only: živá metodika se neporovnává (AUDIT-SNAPSHOT-URGENT-1)."""
    del methodology_drafts  # záměrně ignorováno — snapshot je zdroj pravdy
    if audit.methodology_source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT:
        return False
    if audit.methodology_generation != AUDIT_METHODOLOGY_GENERATION_LEGACY_V1:
        return False
    if audit.questions_frozen_at is None:
        return False
    reasons = diagnose_frozen_snapshot_db_only(
        audit,
        snapshot_rows=snapshot_rows,
        control_results=control_results,
        require_manifest=True,
    )
    return not reasons


def _diagnose_incomplete_legacy_snapshot(
    audit: Audit,
    *,
    snapshot_rows: list[AuditQuestionSnapshot],
    control_results: list[ControlResult],
) -> str:
    """Přesný důvod nekonzistence pro legacy snapshot / částečný stav."""
    source = str(audit.methodology_source or "").strip()
    generation = str(audit.methodology_generation or "").strip()
    parts: list[str] = [
        f"source={source or 'NULL'}",
        f"generation={generation or 'NULL'}",
        f"frozen_at={'set' if audit.questions_frozen_at else 'NULL'}",
        f"snapshots={len(snapshot_rows)}",
        f"control_results={len(control_results)}",
    ]
    if (
        source == AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
        and generation == AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        and audit.questions_frozen_at is not None
    ):
        reasons = diagnose_frozen_snapshot_db_only(
            audit,
            snapshot_rows=snapshot_rows,
            control_results=control_results,
            require_manifest=True,
        )
        if reasons:
            parts.append("důvody=" + " | ".join(reasons))
        else:
            parts.append("důvody=neznámé")
    elif source or generation or audit.questions_frozen_at is not None or snapshot_rows:
        parts.append("důvody=částečný / nekonzistentní stav markerů a snapshotů")
    return " ".join(parts)


AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE = "legacy_complete"
AUDIT_BACKFILL_STATUS_OTHER_GENERATION = "other_generation"
AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL = "needs_backfill"
AUDIT_BACKFILL_STATUS_INCONSISTENT = "inconsistent"


@dataclass(frozen=True)
class AuditBackfillIntegrityItem:
    audit_id: int
    status: str
    detail: str = ""


@dataclass(frozen=True)
class AuditBackfillIntegrityReport:
    items: tuple[AuditBackfillIntegrityItem, ...]
    needs_backfill_ids: tuple[int, ...]
    inconsistent_ids: tuple[int, ...]
    other_generation_ids: tuple[int, ...]
    legacy_complete_ids: tuple[int, ...]

    @property
    def all_satisfied(self) -> bool:
        return not self.needs_backfill_ids and not self.inconsistent_ids


def classify_audit_backfill_state(
    audit: Audit,
    *,
    snapshot_rows: list[AuditQuestionSnapshot],
    control_results: list[ControlResult],
    methodology_drafts: list[AuditQuestionSnapshotDraft] | None = None,
) -> AuditBackfillIntegrityItem:
    """Klasifikace auditu vůči legacy backfillu — jiné generace se nemění."""
    del methodology_drafts
    generation = str(audit.methodology_generation or "").strip()
    source = str(audit.methodology_source or "").strip()

    if generation and generation != AUDIT_METHODOLOGY_GENERATION_LEGACY_V1:
        return AuditBackfillIntegrityItem(
            audit_id=audit.id,
            status=AUDIT_BACKFILL_STATUS_OTHER_GENERATION,
            detail=f"methodology_generation={generation}",
        )

    if _is_audit_snapshot_complete(
        audit,
        snapshot_rows=snapshot_rows,
        control_results=control_results,
    ):
        return AuditBackfillIntegrityItem(
            audit_id=audit.id,
            status=AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE,
        )

    pristine = (
        not source
        and not generation
        and audit.questions_frozen_at is None
        and not snapshot_rows
    )
    if pristine:
        return AuditBackfillIntegrityItem(
            audit_id=audit.id,
            status=AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL,
            detail="pre_backfill",
        )

    return AuditBackfillIntegrityItem(
        audit_id=audit.id,
        status=AUDIT_BACKFILL_STATUS_INCONSISTENT,
        detail=_diagnose_incomplete_legacy_snapshot(
            audit,
            snapshot_rows=snapshot_rows,
            control_results=control_results,
        ),
    )


def assess_legacy_backfill_integrity(
    *,
    knowledge_tree=None,
) -> AuditBackfillIntegrityReport:
    """Ověří skutečný stav DB vůči legacy backfillu (ne jen migration_state)."""
    if knowledge_tree is None:
        knowledge_tree = audit_knowledge_service.get_knowledge_tree(ensure=True)

    items: list[AuditBackfillIntegrityItem] = []
    with get_session() as session:
        audits = list(session.scalars(select(Audit).order_by(Audit.id)))
        for audit in audits:
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
            planned = _planned_process_ids_for_audit(audit)
            methodology = audit_question_snapshot_service.build_snapshot_for_audit(
                audit.id,
                planned_process_ids=planned,
                ensure=False,
                knowledge_tree=knowledge_tree,
            )
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            items.append(
                classify_audit_backfill_state(
                    audit,
                    snapshot_rows=snaps,
                    control_results=results,
                    methodology_drafts=methodology,
                )
            )

    return AuditBackfillIntegrityReport(
        items=tuple(items),
        needs_backfill_ids=tuple(
            i.audit_id
            for i in items
            if i.status == AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL
        ),
        inconsistent_ids=tuple(
            i.audit_id
            for i in items
            if i.status == AUDIT_BACKFILL_STATUS_INCONSISTENT
        ),
        other_generation_ids=tuple(
            i.audit_id
            for i in items
            if i.status == AUDIT_BACKFILL_STATUS_OTHER_GENERATION
        ),
        legacy_complete_ids=tuple(
            i.audit_id
            for i in items
            if i.status == AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE
        ),
    )


def _match_result_to_drafts(
    result: ControlResult,
    drafts: list[AuditQuestionSnapshotDraft],
) -> AuditQuestionSnapshotDraft | None:
    return match_result_to_snapshot_drafts(result, drafts)


def _validate_audit_snapshot(
    audit: Audit,
    *,
    drafts: list[AuditQuestionSnapshotDraft],
    control_results: list[ControlResult],
    methodology_drafts: list[AuditQuestionSnapshotDraft],
) -> None:
    draft_keys = {
        snapshot_key(item.process_id, item.section_id, item.assertion_id) for item in drafts
    }
    for method in methodology_drafts:
        key = snapshot_key(method.process_id, method.section_id, method.assertion_id)
        if key not in draft_keys:
            raise AuditSnapshotBackfillError(
                f"Audit {audit.id}: snapshot neobsahuje metodickou otázku "
                f"{key}."
            )

    for result in control_results:
        if _match_result_to_drafts(result, drafts) is None:
            raise AuditSnapshotBackfillError(
                f"Audit {audit.id}: control_result id={result.id} "
                f"(cp={result.source_control_point_id!r}) nemá snapshotový protějšek."
            )

    # Unikátnost klíčů ve snapshotu.
    if len(draft_keys) != len(drafts):
        raise AuditSnapshotBackfillError(
            f"Audit {audit.id}: duplicitní klíče ve snapshotu."
        )


def _count_table(session, table: str) -> int:
    return int(session.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)


def _control_results_fingerprint(session) -> tuple[tuple, ...]:
    """Hodnotový otisk control_results (bez změny po aditivním backfillu)."""
    rows = list(
        session.scalars(select(ControlResult).order_by(ControlResult.id))
    )
    return tuple(
        (
            int(row.id),
            str(row.entity_type or ""),
            int(row.entity_id or 0),
            str(row.source_area_id or ""),
            str(row.source_area_label or ""),
            str(row.source_section_id or ""),
            str(row.source_section_label or ""),
            str(row.source_control_point_id or ""),
            str(row.source_control_point_label or ""),
            str(row.result or ""),
            bool(row.shared_experience),
            str(row.photo_path or ""),
            str(row.note or ""),
            str(row.recorded_by_name or ""),
        )
        for row in rows
    )


def _control_results_schema_ready(db_path: Path) -> bool:
    """True, pokud control_results má sloupce potřebné pro historický snapshot."""
    path = Path(db_path)
    if not path.is_file() or not sqlite_table_exists(path, "control_results"):
        return True  # prázdná / bez výsledků — backfill může běžet
    required = {
        "entity_type",
        "entity_id",
        "source_area_id",
        "source_area_label",
        "source_section_id",
        "source_section_label",
        "source_control_point_id",
        "source_control_point_label",
        "result",
    }
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(control_results)")}
    finally:
        conn.close()
    return required.issubset(cols)


def prepare_audit_snapshot_backfill(
    *,
    workspace_root: Path | None = None,
    database_path: Path | None = None,
    settings_path: Path | None = None,
) -> AuditSnapshotBackfillResult:
    """
    Atomický backfill snapshotů všech existujících auditů.

    Návštěvy bez audit_id se nesnapshotují. UI/export/metodika se nemění.
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
        return AuditSnapshotBackfillResult(
            migrated=False,
            pre_migration_backup_path=None,
            processed_audits=0,
            skipped_audits=0,
            visits_without_audit=0,
            report=(),
            skipped_reason="schema_not_ready",
        )

    from moduly.audity.sluzby.audit_snapshot_scope_migration import ensure_scope_column
    from moduly.audity.sluzby.audit_snapshot_integrity_service import (
        ensure_integrity_columns,
    )

    ensure_scope_column(database_path)
    if ensure_integrity_columns(database_path):
        reconfigure_database_engine(force=True)

    if not _control_results_schema_ready(database_path):
        logger.warning(
            "AUDIT-SNAPSHOT-1a: control_results schema není připravené — backfill odložen."
        )
        return AuditSnapshotBackfillResult(
            migrated=False,
            pre_migration_backup_path=None,
            processed_audits=0,
            skipped_audits=0,
            visits_without_audit=0,
            report=(),
            skipped_reason="control_results_schema_not_ready",
        )

    if is_migration_in_progress(workspace_root, TRANSITION_ID):
        state = read_migration_state(workspace_root)
        backup = (state.get("in_progress") or {}).get("pre_migration_backup")
        mark_migration_failed(
            workspace_root,
            backup_path=Path(backup) if backup else None,
            transition_id=TRANSITION_ID,
            error="interrupted_backfill",
        )
        logger.warning(
            "AUDIT-SNAPSHOT-1a: nedokončený backfill uvolněn pro opakování. Záloha: %s",
            backup or "(nenalezena)",
        )

    # --- Inventura + ověření skutečného stavu DB (ne jen migration_state) ---
    reconfigure_database_engine(force=True)
    knowledge_tree = audit_knowledge_service.get_knowledge_tree(ensure=True)

    with get_session() as session:
        audits = list(session.scalars(select(Audit).order_by(Audit.id)))
        visits_without_audit = len(
            list(
                session.scalars(
                    select(AuditProgramVisit).where(
                        AuditProgramVisit.audit_id.is_(None)
                    )
                )
            )
        )

        inventory: list[AuditBackfillInventoryItem] = []
        prepared: list[
            tuple[
                Audit,
                list[AuditQuestionSnapshotDraft],
                list[AuditQuestionSnapshotDraft],
                list[ControlResult],
                str,
            ]
        ] = []
        integrity_items: list[AuditBackfillIntegrityItem] = []

        baseline = {
            "audits": _count_table(session, "audits"),
            "control_results": _count_table(session, "control_results"),
            "findings": _count_table(session, "findings"),
            "tasks": _count_table(session, "tasks"),
            "audit_programs": _count_table(session, "audit_programs"),
            "audit_program_visits": _count_table(session, "audit_program_visits"),
            "audit_program_visit_processes": _count_table(
                session, "audit_program_visit_processes"
            ),
            "audit_verification_overrides": _count_table(
                session, "audit_verification_overrides"
            ),
        }
        control_results_fingerprint_before = _control_results_fingerprint(session)

        for audit in audits:
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
            planned = _planned_process_ids_for_audit(audit)
            methodology = audit_question_snapshot_service.build_snapshot_for_audit(
                audit.id,
                planned_process_ids=planned,
                ensure=False,
                knowledge_tree=knowledge_tree,
            )
            historical = (
                audit_question_snapshot_service.merge_methodology_with_control_results(
                    audit.id,
                    methodology_drafts=methodology,
                    control_results=results,
                    question_kind=AUDIT_QUESTION_KIND_LEGACY,
                )
            )
            existing_snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            classification = classify_audit_backfill_state(
                audit,
                snapshot_rows=existing_snaps,
                control_results=results,
                methodology_drafts=methodology,
            )
            integrity_items.append(classification)
            orphan_count = sum(1 for item in historical if item.is_orphan)
            inventory.append(
                AuditBackfillInventoryItem(
                    audit_id=audit.id,
                    status=str(audit.status or ""),
                    workplace_id=audit.workplace_id,
                    program_id=audit.program_id,
                    program_visit_id=audit.program_visit_id,
                    control_results_count=len(results),
                    planned_process_count=len(planned or ()),
                    methodology_question_count=len(methodology),
                    orphan_result_count=orphan_count,
                    already_complete=(
                        classification.status == AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE
                    ),
                )
            )
            for row in results:
                session.expunge(row)
            session.expunge(audit)
            prepared.append(
                (audit, methodology, historical, results, classification.status)
            )

    integrity = AuditBackfillIntegrityReport(
        items=tuple(integrity_items),
        needs_backfill_ids=tuple(
            i.audit_id
            for i in integrity_items
            if i.status == AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL
        ),
        inconsistent_ids=tuple(
            i.audit_id
            for i in integrity_items
            if i.status == AUDIT_BACKFILL_STATUS_INCONSISTENT
        ),
        other_generation_ids=tuple(
            i.audit_id
            for i in integrity_items
            if i.status == AUDIT_BACKFILL_STATUS_OTHER_GENERATION
        ),
        legacy_complete_ids=tuple(
            i.audit_id
            for i in integrity_items
            if i.status == AUDIT_BACKFILL_STATUS_LEGACY_COMPLETE
        ),
    )

    logger.info(
        "AUDIT-SNAPSHOT-1a inventura: audits=%s visits_without_audit=%s "
        "legacy_complete=%s needs_backfill=%s inconsistent=%s other_generation=%s",
        len(inventory),
        visits_without_audit,
        len(integrity.legacy_complete_ids),
        len(integrity.needs_backfill_ids),
        len(integrity.inconsistent_ids),
        len(integrity.other_generation_ids),
    )
    for item in inventory:
        logger.info(
            "AUDIT-SNAPSHOT-1a audit id=%s status=%s workplace_id=%s program_id=%s "
            "control_results=%s planned_processes=%s methodology_questions=%s "
            "orphan_results=%s already_complete=%s",
            item.audit_id,
            item.status,
            item.workplace_id,
            item.program_id,
            item.control_results_count,
            item.planned_process_count,
            item.methodology_question_count,
            item.orphan_result_count,
            item.already_complete,
        )

    if integrity.inconsistent_ids:
        details = "; ".join(
            f"id={item.audit_id} ({item.detail})"
            for item in integrity.items
            if item.status == AUDIT_BACKFILL_STATUS_INCONSISTENT
        )
        raise AuditSnapshotBackfillError(
            "AUDIT-SNAPSHOT-1a: nekonzistentní / částečný snapshot. "
            "Automatická destruktivní oprava se nespouští. "
            f"Audity: {details}. Obnovte zálohu nebo opravte data ručně."
        )

    claimed_complete = is_transition_complete(workspace_root, TRANSITION_ID)

    if not integrity.needs_backfill_ids:
        if not claimed_complete:
            mark_migration_complete(
                workspace_root, backup_path=None, transition_id=TRANSITION_ID
            )
        report = tuple(
            AuditBackfillReportItem(
                audit_id=audit.id,
                status=str(audit.status or ""),
                snapshot_question_count=len(historical),
                questions_with_result=sum(
                    1 for d in historical if d.from_control_result
                ),
                orphan_count=sum(1 for d in historical if d.is_orphan),
                validation_ok=True,
                skipped=True,
                detail=status,
            )
            for audit, _method, historical, _results, status in prepared
        )
        return AuditSnapshotBackfillResult(
            migrated=False,
            pre_migration_backup_path=None,
            processed_audits=0,
            skipped_audits=len(prepared),
            visits_without_audit=visits_without_audit,
            report=report,
            skipped_reason=(
                "transition_already_complete"
                if claimed_complete
                else "all_audits_already_complete"
            ),
        )

    if claimed_complete:
        logger.warning(
            "AUDIT-SNAPSHOT-1a: stav completed, ale DB postrádá backfill "
            "pro audity %s — zneplatňuji complete a opakuji.",
            list(integrity.needs_backfill_ids),
        )
        clear_transition_complete(workspace_root, TRANSITION_ID)

    to_write = [
        row
        for row in prepared
        if row[4] == AUDIT_BACKFILL_STATUS_NEEDS_BACKFILL
    ]

    # Validace před zápisem (v paměti) — jen pristine audity.
    for audit, methodology, historical, results, _status in to_write:
        try:
            _validate_audit_snapshot(
                audit,
                drafts=historical,
                control_results=results,
                methodology_drafts=methodology,
            )
        except AuditSnapshotBackfillError:
            raise
        except Exception as exc:
            raise AuditSnapshotBackfillError(
                f"Audit {audit.id}: validace selhala: {exc}"
            ) from exc

    target = allocate_backfill_backup_path(backups_dir)
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
            "Nepodařilo se vytvořit předmigrační zálohu AUDIT-SNAPSHOT-1a. "
            "Backfill nebyl spuštěn."
        ) from exc

    logger.info("AUDIT-SNAPSHOT-1a: vytvořena předmigrační záloha: %s", backup_path)
    mark_migration_in_progress(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )

    frozen_at = datetime.now()
    report_items: list[AuditBackfillReportItem] = []
    write_ids = {audit.id for audit, *_rest in to_write}

    try:
        with get_session() as session:
            try:
                for audit_detached, methodology, historical, results, status in prepared:
                    audit = session.get(Audit, audit_detached.id)
                    if audit is None:
                        raise AuditSnapshotBackfillError(
                            f"Audit {audit_detached.id} zmizel během backfille."
                        )

                    if audit_detached.id not in write_ids:
                        report_items.append(
                            AuditBackfillReportItem(
                                audit_id=audit.id,
                                status=str(audit.status or ""),
                                snapshot_question_count=len(historical),
                                questions_with_result=sum(
                                    1 for d in historical if d.from_control_result
                                ),
                                orphan_count=sum(1 for d in historical if d.is_orphan),
                                validation_ok=True,
                                skipped=True,
                                detail=status,
                            )
                        )
                        continue

                    # Pristine pre-backfill: jen INSERT (žádné mazání existujících snapshotů).
                    existing = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit.id
                            )
                        )
                    )
                    if existing:
                        raise AuditSnapshotBackfillError(
                            f"Audit {audit.id}: očekáván prázdný snapshot před backfillem, "
                            f"nalezeno {len(existing)} řádků. Destruktivní přepis se neprovádí."
                        )

                    for draft in historical:
                        session.add(
                            AuditQuestionSnapshot(
                                audit_id=audit.id,
                                process_id=draft.process_id,
                                process_name=draft.process_name,
                                section_id=draft.section_id,
                                section_name=draft.section_name,
                                assertion_id=draft.assertion_id,
                                assertion_text=draft.assertion_text,
                                verification_type=draft.verification_type,
                                severity=draft.severity,
                                question_kind=draft.question_kind
                                or AUDIT_QUESTION_KIND_LEGACY,
                                display_order=draft.display_order,
                                is_in_scope=bool(draft.is_in_scope)
                                and not bool(draft.is_orphan),
                                created_at=frozen_at,
                            )
                        )

                    audit.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                    audit.questions_frozen_at = frozen_at
                    audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                    audit.updated_at = frozen_at
                    session.flush()
                    written_snaps = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit.id
                            )
                        )
                    )
                    apply_snapshot_integrity_manifest(audit, written_snaps)

                    report_items.append(
                        AuditBackfillReportItem(
                            audit_id=audit.id,
                            status=str(audit.status or ""),
                            snapshot_question_count=len(historical),
                            questions_with_result=sum(
                                1 for d in historical if d.from_control_result
                            ),
                            orphan_count=sum(1 for d in historical if d.is_orphan),
                            validation_ok=True,
                            skipped=False,
                            detail="written",
                        )
                    )

                session.flush()

                after = {
                    "audits": _count_table(session, "audits"),
                    "control_results": _count_table(session, "control_results"),
                    "findings": _count_table(session, "findings"),
                    "tasks": _count_table(session, "tasks"),
                    "audit_programs": _count_table(session, "audit_programs"),
                    "audit_program_visits": _count_table(session, "audit_program_visits"),
                    "audit_program_visit_processes": _count_table(
                        session, "audit_program_visit_processes"
                    ),
                    "audit_verification_overrides": _count_table(
                        session, "audit_verification_overrides"
                    ),
                }
                if after != baseline:
                    raise AuditSnapshotBackfillError(
                        f"Počty entit se změnily během backfille: before={baseline} after={after}"
                    )

                fingerprint_after = _control_results_fingerprint(session)
                if fingerprint_after != control_results_fingerprint_before:
                    raise AuditSnapshotBackfillError(
                        "Hodnoty control_results se změnily během backfille."
                    )

                for audit_detached, methodology, historical, results, status in prepared:
                    if audit_detached.id not in write_ids:
                        continue
                    snaps = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit_detached.id
                            )
                        )
                    )
                    orphan_keys = {
                        snapshot_key(d.process_id, d.section_id, d.assertion_id)
                        for d in historical
                        if d.is_orphan
                    }
                    snap_drafts = [
                        AuditQuestionSnapshotDraft(
                            audit_id=audit_detached.id,
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
                            from_control_result=True,
                            is_orphan=snapshot_key(
                                row.process_id, row.section_id, row.assertion_id
                            )
                            in orphan_keys,
                        )
                        for row in snaps
                    ]
                    _validate_audit_snapshot(
                        audit_detached,
                        drafts=snap_drafts,
                        control_results=results,
                        methodology_drafts=methodology,
                    )
                    db_audit = session.get(Audit, audit_detached.id)
                    if (
                        db_audit is None
                        or db_audit.methodology_source
                        != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                        or db_audit.methodology_generation
                        != AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                        or db_audit.questions_frozen_at is None
                    ):
                        raise AuditSnapshotBackfillError(
                            f"Audit {audit_detached.id}: označení snapshotu není kompletní."
                        )

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
            "AUDIT-SNAPSHOT-1a: backfill selhal, transakce vrácena. Záloha: %s. Detail: %s",
            backup_path,
            exc,
        )
        if isinstance(exc, AuditSnapshotBackfillError):
            raise
        raise AuditSnapshotBackfillError(
            f"Backfill AUDIT-SNAPSHOT-1a selhal. Záloha: {backup_path}\nDetail: {exc}"
        ) from exc

    mark_migration_complete(
        workspace_root, backup_path=backup_path, transition_id=TRANSITION_ID
    )

    for item in report_items:
        logger.info(
            "AUDIT-SNAPSHOT-1a report audit_id=%s status=%s questions=%s "
            "with_result=%s orphans=%s ok=%s skipped=%s detail=%s",
            item.audit_id,
            item.status,
            item.snapshot_question_count,
            item.questions_with_result,
            item.orphan_count,
            item.validation_ok,
            item.skipped,
            item.detail,
        )

    processed = sum(1 for item in report_items if not item.skipped)
    skipped = sum(1 for item in report_items if item.skipped)
    logger.info(
        "AUDIT-SNAPSHOT-1a: dokončeno. processed=%s skipped=%s backup=%s",
        processed,
        skipped,
        backup_path,
    )
    return AuditSnapshotBackfillResult(
        migrated=processed > 0,
        pre_migration_backup_path=backup_path,
        processed_audits=processed,
        skipped_audits=skipped,
        visits_without_audit=visits_without_audit,
        report=tuple(report_items),
        skipped_reason=None,
    )
