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


def _is_audit_snapshot_complete(
    audit: Audit,
    *,
    snapshot_rows: list[AuditQuestionSnapshot],
    control_results: list[ControlResult],
    methodology_drafts: list[AuditQuestionSnapshotDraft],
) -> bool:
    if audit.methodology_source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT:
        return False
    if audit.methodology_generation != AUDIT_METHODOLOGY_GENERATION_LEGACY_V1:
        return False
    if audit.questions_frozen_at is None:
        return False
    if not snapshot_rows and (methodology_drafts or control_results):
        return False

    snap_keys = {
        snapshot_key(row.process_id, row.section_id, row.assertion_id)
        for row in snapshot_rows
    }
    for draft in methodology_drafts:
        if snapshot_key(draft.process_id, draft.section_id, draft.assertion_id) not in snap_keys:
            return False

    for result in control_results:
        id_key = snapshot_key(
            result.source_area_id,
            result.source_section_id,
            result.source_control_point_id,
        )
        if id_key[2] and id_key in snap_keys:
            continue
        # Orphan / label fallback: stačí assertion_id shoda + area/section text/id.
        matched = False
        for row in snapshot_rows:
            if str(row.assertion_id or "").strip() != str(
                result.source_control_point_id or ""
            ).strip():
                continue
            if (
                str(row.process_id or "").strip()
                in {
                    str(result.source_area_id or "").strip(),
                    f"orphan_process_{result.id}",
                }
                or str(row.process_name or "").strip()
                == str(result.source_area_label or "").strip()
            ):
                matched = True
                break
        if not matched:
            # synthetic orphan key
            synthetic = snapshot_key(
                str(result.source_area_id or "").strip() or f"orphan_process_{result.id}",
                str(result.source_section_id or "").strip()
                or f"orphan_section_{result.id}",
                str(result.source_control_point_id or "").strip()
                or f"orphan_cr_{result.id}",
            )
            if synthetic not in snap_keys:
                return False
    return True


def _match_result_to_drafts(
    result: ControlResult,
    drafts: list[AuditQuestionSnapshotDraft],
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

    if is_transition_complete(workspace_root, TRANSITION_ID):
        # Idempotentní no-op, pokud jsou všechny audity kompletní.
        with get_session() as session:
            audits = list(session.scalars(select(Audit).order_by(Audit.id)))
            incomplete = [
                audit.id
                for audit in audits
                if audit.methodology_source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                or audit.methodology_generation != AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                or audit.questions_frozen_at is None
            ]
        if not incomplete:
            return AuditSnapshotBackfillResult(
                migrated=False,
                pre_migration_backup_path=None,
                processed_audits=0,
                skipped_audits=len(audits),
                visits_without_audit=0,
                report=(),
                skipped_reason="transition_already_complete",
            )
        logger.warning(
            "AUDIT-SNAPSHOT-1a: stav completed, ale %s auditů není kompletních — opakuji.",
            len(incomplete),
        )

    # --- Inventura (read-only) ---
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
                bool,
            ]
        ] = []

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
        photo_paths_before = {
            int(row.id): str(row.photo_path or "")
            for row in session.scalars(select(ControlResult)).all()
        }

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
            complete = _is_audit_snapshot_complete(
                audit,
                snapshot_rows=existing_snaps,
                control_results=results,
                methodology_drafts=methodology,
            )
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
                    already_complete=complete,
                )
            )
            for row in results:
                session.expunge(row)
            session.expunge(audit)
            prepared.append((audit, methodology, historical, results, complete))

    logger.info(
        "AUDIT-SNAPSHOT-1a inventura: audits=%s visits_without_audit=%s",
        len(inventory),
        visits_without_audit,
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

    to_write = [row for row in prepared if not row[4]]
    if not to_write:
        mark_migration_complete(
            workspace_root, backup_path=None, transition_id=TRANSITION_ID
        )
        report = tuple(
            AuditBackfillReportItem(
                audit_id=audit.id,
                status=str(audit.status or ""),
                snapshot_question_count=len(historical),
                questions_with_result=sum(1 for d in historical if d.from_control_result),
                orphan_count=sum(1 for d in historical if d.is_orphan),
                validation_ok=True,
                skipped=True,
                detail="already_complete",
            )
            for audit, _method, historical, _results, _complete in prepared
        )
        return AuditSnapshotBackfillResult(
            migrated=False,
            pre_migration_backup_path=None,
            processed_audits=0,
            skipped_audits=len(prepared),
            visits_without_audit=visits_without_audit,
            report=report,
            skipped_reason="all_audits_already_complete",
        )

    # Validace před zápisem (v paměti).
    for audit, methodology, historical, results, _complete in to_write:
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

    try:
        with get_session() as session:
            try:
                for audit_detached, methodology, historical, results, complete in prepared:
                    audit = session.get(Audit, audit_detached.id)
                    if audit is None:
                        raise AuditSnapshotBackfillError(
                            f"Audit {audit_detached.id} zmizel během backfille."
                        )

                    if complete:
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
                                detail="already_complete",
                            )
                        )
                        continue

                    # Neúplný stav — nahradit snapshot řádky atomicky.
                    existing = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit.id
                            )
                        )
                    )
                    for row in existing:
                        session.delete(row)
                    session.flush()

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
                                created_at=frozen_at,
                            )
                        )

                    audit.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                    audit.questions_frozen_at = frozen_at
                    audit.methodology_generation = AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                    audit.updated_at = frozen_at

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

                # Povinná validace počtů před COMMIT.
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

                photo_paths_after = {
                    int(row.id): str(row.photo_path or "")
                    for row in session.scalars(select(ControlResult)).all()
                }
                if photo_paths_after != photo_paths_before:
                    raise AuditSnapshotBackfillError(
                        "Cesty fotografií control_results se změnily během backfille."
                    )

                # Každý zapsaný audit: snapshot pokrývá CR.
                for audit_detached, methodology, historical, results, complete in prepared:
                    if complete:
                        continue
                    snaps = list(
                        session.scalars(
                            select(AuditQuestionSnapshot).where(
                                AuditQuestionSnapshot.audit_id == audit_detached.id
                            )
                        )
                    )
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
                            is_orphan=False,
                        )
                        for row in snaps
                    ]
                    # Obnov is_orphan podle historical
                    orphan_keys = {
                        snapshot_key(d.process_id, d.section_id, d.assertion_id)
                        for d in historical
                        if d.is_orphan
                    }
                    snap_drafts = [
                        AuditQuestionSnapshotDraft(
                            audit_id=d.audit_id,
                            process_id=d.process_id,
                            process_name=d.process_name,
                            section_id=d.section_id,
                            section_name=d.section_name,
                            assertion_id=d.assertion_id,
                            assertion_text=d.assertion_text,
                            verification_type=d.verification_type,
                            severity=d.severity,
                            question_kind=d.question_kind,
                            display_order=d.display_order,
                            from_control_result=True,
                            is_orphan=snapshot_key(
                                d.process_id, d.section_id, d.assertion_id
                            )
                            in orphan_keys,
                        )
                        for d in snap_drafts
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
