"""Bezpečné odstranění konkrétního neúplného testovacího auditu (URGENT-2).

Nabízí výslovně potvrzené odstranění pouze pro audit id=7 bez business dat.
Žádné obecné automatické mazání ostatních neúplných auditů.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from core.backup.constants import BACKUP_EXTENSION
from core.database.session import get_session
from core.database.upgrade_guard import (
    MigrationGuardError,
    PreMigrationBackupError,
    create_verified_pre_migration_backup,
)
from core.shared.constants import ENTITY_AUDITY
from core.shared.modely.control_result import ControlResult
from core.shared.modely.finding import Finding
from core.version import APP_VERSION
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_commission_member import AuditCommissionMember
from moduly.audity.modely.audit_program import AuditProgramVisit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.modely.audit_verification_override import AuditVerificationOverride
from moduly.ukoly.modely.task import Task

logger = logging.getLogger(__name__)

# Konkrétní testovací záznam potvrzený uživatelem — žádné obecné mazání.
TARGET_INCOMPLETE_MANUAL_AUDIT_ID = 7
BACKUP_NAME_PREFIX = "pre_incomplete_manual_audit_cleanup"

# Přílohy mohou být pod oběma klíči (historicky).
_ATTACHMENT_ENTITY_TYPES = (ENTITY_AUDITY, "audit")


class IncompleteManualAuditCleanupError(MigrationGuardError):
    """Nelze pokračovat se startem — neúplný audit / zrušené odstranění."""


@dataclass(frozen=True)
class IncompleteManualAuditDiagnostics:
    audit_id: int
    workplace_name: str
    audit_date_text: str
    snapshot_count: int
    control_results_count: int
    findings_count: int
    tasks_count: int
    photos_count: int
    attachments_count: int
    commission_count: int
    missing_markers: tuple[str, ...]
    eligible_for_confirmed_cleanup: bool
    ineligibility_reasons: tuple[str, ...] = ()


@dataclass
class IncompleteManualAuditCleanupResult:
    deleted: bool
    backup_path: Path | None = None
    deleted_rows: dict[str, int] = field(default_factory=dict)
    message: str = ""


def allocate_incomplete_manual_audit_backup_path(
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
    raise IncompleteManualAuditCleanupError(
        "Nelze přidělit unikátní název zálohy před odstraněním neúplného auditu."
    )


def _count_attachments(session, audit_id: int) -> int:
    from core.models.attachment import Attachment

    total = 0
    for entity_type in _ATTACHMENT_ENTITY_TYPES:
        rows = list(
            session.scalars(
                select(Attachment).where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id == audit_id,
                )
            )
        )
        total += len(rows)
    return total


def _count_tasks_for_audit(session, audit_id: int, findings: list[Finding]) -> int:
    task_ids: set[int] = set()
    for finding in findings:
        if finding.task_id:
            task_ids.add(int(finding.task_id))
    direct = list(
        session.scalars(
            select(Task).where(
                Task.source_module.in_((ENTITY_AUDITY, "audit")),
                Task.source_record_id == audit_id,
            )
        )
    )
    for task in direct:
        task_ids.add(int(task.id))
    return len(task_ids)


def collect_incomplete_manual_audit_diagnostics(
    audit_id: int = TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
) -> IncompleteManualAuditDiagnostics | None:
    """Vrátí diagnostiku cílového auditu, nebo None pokud audit neexistuje."""
    with get_session() as session:
        audit = session.get(Audit, int(audit_id))
        if audit is None:
            return None

        snaps = list(
            session.scalars(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
        )
        results = list(
            session.scalars(
                select(ControlResult).where(
                    ControlResult.entity_type == ENTITY_AUDITY,
                    ControlResult.entity_id == audit.id,
                )
            )
        )
        findings = list(
            session.scalars(
                select(Finding).where(
                    Finding.entity_type == ENTITY_AUDITY,
                    Finding.entity_id == audit.id,
                )
            )
        )
        commission = list(
            session.scalars(
                select(AuditCommissionMember).where(
                    AuditCommissionMember.audit_id == audit.id
                )
            )
        )

        photos = sum(1 for row in results if str(row.photo_path or "").strip())
        attachments = _count_attachments(session, audit.id)
        tasks_count = _count_tasks_for_audit(session, audit.id, findings)

        missing: list[str] = []
        if not str(audit.methodology_source or "").strip():
            missing.append("methodology_source")
        if not str(audit.methodology_generation or "").strip():
            missing.append("methodology_generation")
        if audit.questions_frozen_at is None:
            missing.append("questions_frozen_at")

        reasons: list[str] = []
        if int(audit.id) != TARGET_INCOMPLETE_MANUAL_AUDIT_ID:
            reasons.append(
                f"audit id={audit.id} není cílový testovací záznam "
                f"(očekáváno id={TARGET_INCOMPLETE_MANUAL_AUDIT_ID})"
            )
        if str(audit.methodology_source or "").strip():
            reasons.append("methodology_source není NULL")
        if str(audit.methodology_generation or "").strip():
            reasons.append("methodology_generation není NULL")
        if audit.questions_frozen_at is not None:
            reasons.append("questions_frozen_at není NULL")
        if not snaps:
            reasons.append("chybí snapshotové řádky (neúplný stav bez snapshotů)")
        if results:
            reasons.append(f"existují control_results ({len(results)})")
        if findings:
            reasons.append(f"existují zjištění ({len(findings)})")
        if tasks_count:
            reasons.append(f"existují úkoly ({tasks_count})")
        if photos:
            reasons.append(f"existují fotografie u výsledků ({photos})")
        if attachments:
            reasons.append(f"existují přílohy ({attachments})")

        visit = session.scalars(
            select(AuditProgramVisit).where(AuditProgramVisit.audit_id == audit.id)
        ).first()
        if visit is not None:
            reasons.append(
                f"audit je navázán na návštěvu programu (visit id={visit.id})"
            )

        overrides = list(
            session.scalars(
                select(AuditVerificationOverride).where(
                    AuditVerificationOverride.audit_id == audit.id
                )
            )
        )
        # Override samotný neblokuje, pokud nejsou business data — ale evidujeme.
        del overrides

        audit_date = audit.audit_date or audit.started_at
        date_text = audit_date.isoformat() if audit_date is not None else "(bez data)"

        return IncompleteManualAuditDiagnostics(
            audit_id=int(audit.id),
            workplace_name=str(audit.workplace_name or "").strip() or "(bez provozu)",
            audit_date_text=date_text,
            snapshot_count=len(snaps),
            control_results_count=len(results),
            findings_count=len(findings),
            tasks_count=tasks_count,
            photos_count=photos,
            attachments_count=attachments,
            commission_count=len(commission),
            missing_markers=tuple(missing),
            eligible_for_confirmed_cleanup=not reasons,
            ineligibility_reasons=tuple(reasons),
        )


def format_incomplete_audit_dialog_text(
    diag: IncompleteManualAuditDiagnostics,
) -> str:
    markers = ", ".join(diag.missing_markers) if diag.missing_markers else "(žádné)"
    return (
        "Byl zjištěn neúplný testovací audit bez dokončeného snapshotu v2.\n\n"
        f"ID auditu: {diag.audit_id}\n"
        f"Auditovaný provoz: {diag.workplace_name}\n"
        f"Datum: {diag.audit_date_text}\n"
        f"Snapshotové řádky: {diag.snapshot_count}\n"
        f"Výsledky kontroly: {diag.control_results_count}\n"
        f"Zjištění: {diag.findings_count}\n"
        f"Úkoly: {diag.tasks_count}\n"
        f"Fotografie u výsledků: {diag.photos_count}\n"
        f"Přílohy: {diag.attachments_count}\n"
        f"Členové komise: {diag.commission_count}\n"
        f"Chybějící markery: {markers}\n\n"
        "Před odstraněním se vytvoří ověřená záloha.\n"
        "Odstraněn bude pouze tento testovací audit a jeho neúplné odvozené řádky."
    )


def _ensure_qapplication() -> None:
    from PySide6.QtWidgets import QApplication

    from core.dialogs.message_box import (
        configure_application_for_dialogs,
        install_unified_message_boxes,
    )
    from core.widgets.no_wheel_guards import install_form_wheel_guards

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationVersion(APP_VERSION)
        configure_application_for_dialogs(app)
        install_unified_message_boxes(app)
        install_form_wheel_guards(app)


def prompt_incomplete_manual_audit_cleanup(
    diag: IncompleteManualAuditDiagnostics,
    *,
    parent=None,
) -> bool:
    """
    Zobrazí obnovovací dialog.

    Returns:
        True = uživatel potvrdil odstranění.
        False = Zrušit.
    """
    from PySide6.QtWidgets import QMessageBox

    _ensure_qapplication()
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("Neúplný testovací audit")
    box.setText(format_incomplete_audit_dialog_text(diag))
    delete_btn = box.addButton(
        "Odstranit neúplný testovací audit",
        QMessageBox.DestructiveRole,
    )
    cancel_btn = box.addButton("Zrušit", QMessageBox.RejectRole)
    box.setDefaultButton(cancel_btn)
    box.exec()
    return box.clickedButton() is delete_btn


def delete_incomplete_manual_audit_atomically(
    audit_id: int,
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
    create_backup: bool = True,
) -> IncompleteManualAuditCleanupResult:
    """Záloha (volitelně) + atomické odstranění. Při chybě ROLLBACK / bez mazání."""
    diag = collect_incomplete_manual_audit_diagnostics(audit_id)
    if diag is None:
        raise IncompleteManualAuditCleanupError(
            f"Audit id={audit_id} neexistuje — odstranění se neprovedlo."
        )
    if not diag.eligible_for_confirmed_cleanup:
        detail = "; ".join(diag.ineligibility_reasons) or "neznámý důvod"
        raise IncompleteManualAuditCleanupError(
            "Odstranění neúplného auditu není povoleno.\n\n" + detail
        )

    backup_path: Path | None = None
    if create_backup:
        backups_dir = Path(workspace_root) / "zalohy"
        target = allocate_incomplete_manual_audit_backup_path(backups_dir)
        try:
            backup_path = create_verified_pre_migration_backup(
                target_path=target,
                workspace_root=Path(workspace_root),
                database_path=Path(database_path),
                settings_path=settings_path,
            )
        except PreMigrationBackupError as exc:
            raise IncompleteManualAuditCleanupError(
                "Nepodařilo se vytvořit ověřenou zálohu před odstraněním. "
                "Audit nebyl odstraněn.\n\n"
                f"{exc}"
            ) from exc
        logger.info(
            "AUDIT-SNAPSHOT-URGENT-2: záloha před odstraněním auditu %s: %s",
            audit_id,
            backup_path,
        )

    deleted_rows: dict[str, int] = {}
    with get_session() as session:
        try:
            audit = session.get(Audit, int(audit_id))
            if audit is None:
                raise IncompleteManualAuditCleanupError(
                    f"Audit id={audit_id} zmizel před odstraněním."
                )

            # Znovu ověř bezpečnostní podmínky v transakci.
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == audit.id
                    )
                )
            )
            results = list(
                session.scalars(
                    select(ControlResult).where(
                        ControlResult.entity_type == ENTITY_AUDITY,
                        ControlResult.entity_id == audit.id,
                    )
                )
            )
            findings = list(
                session.scalars(
                    select(Finding).where(
                        Finding.entity_type == ENTITY_AUDITY,
                        Finding.entity_id == audit.id,
                    )
                )
            )
            if (
                int(audit.id) != TARGET_INCOMPLETE_MANUAL_AUDIT_ID
                or str(audit.methodology_source or "").strip()
                or str(audit.methodology_generation or "").strip()
                or audit.questions_frozen_at is not None
                or not snaps
                or results
                or findings
            ):
                raise IncompleteManualAuditCleanupError(
                    "Stav auditu se změnil — odstranění bylo zrušeno (rollback)."
                )

            from core.models.attachment import Attachment

            attachments: list = []
            for entity_type in _ATTACHMENT_ENTITY_TYPES:
                attachments.extend(
                    list(
                        session.scalars(
                            select(Attachment).where(
                                Attachment.entity_type == entity_type,
                                Attachment.entity_id == audit.id,
                            )
                        )
                    )
                )
            if attachments:
                raise IncompleteManualAuditCleanupError(
                    "Audit má přílohy — odstranění touto cestou není povoleno."
                )

            commission = list(
                session.scalars(
                    select(AuditCommissionMember).where(
                        AuditCommissionMember.audit_id == audit.id
                    )
                )
            )
            overrides = list(
                session.scalars(
                    select(AuditVerificationOverride).where(
                        AuditVerificationOverride.audit_id == audit.id
                    )
                )
            )
            visits = list(
                session.scalars(
                    select(AuditProgramVisit).where(
                        AuditProgramVisit.audit_id == audit.id
                    )
                )
            )
            if visits:
                raise IncompleteManualAuditCleanupError(
                    "Audit je navázán na program — odstranění touto cestou není povoleno."
                )

            for row in snaps:
                session.delete(row)
            deleted_rows["audit_question_snapshots"] = len(snaps)

            for row in commission:
                session.delete(row)
            deleted_rows["audit_commission_members"] = len(commission)

            for row in overrides:
                session.delete(row)
            deleted_rows["audit_verification_overrides"] = len(overrides)

            deleted_rows["control_results"] = 0
            deleted_rows["findings"] = 0
            deleted_rows["attachments"] = 0

            session.delete(audit)
            deleted_rows["audits"] = 1

            session.commit()
        except Exception:
            session.rollback()
            raise

    logger.info(
        "AUDIT-SNAPSHOT-URGENT-2: odstraněn neúplný testovací audit id=%s, řádky=%s, záloha=%s",
        audit_id,
        deleted_rows,
        backup_path,
    )
    return IncompleteManualAuditCleanupResult(
        deleted=True,
        backup_path=backup_path,
        deleted_rows=deleted_rows,
        message=f"Audit id={audit_id} byl bezpečně odstraněn.",
    )


def offer_incomplete_manual_audit_cleanup_at_startup(
    *,
    workspace_root: Path,
    database_path: Path,
    settings_path: Path | None = None,
    interactive: bool = True,
    auto_confirm: bool | None = None,
) -> IncompleteManualAuditCleanupResult | None:
    """
    Při startu: pokud existuje cílový neúplný audit id=7, nabídne odstranění.

    - Zrušit / odmítnutí → MigrationGuardError (start se zastaví, nic se nemění).
    - Neeligibilní neúplný stav → diagnostika + MigrationGuardError.
    - Audit neexistuje → None (pokračovat).
    """
    from moduly.audity.sluzby.audit_snapshot_backfill_service import (
        AUDIT_BACKFILL_STATUS_INCONSISTENT,
        assess_legacy_backfill_integrity,
    )

    diag = collect_incomplete_manual_audit_diagnostics(
        TARGET_INCOMPLETE_MANUAL_AUDIT_ID
    )
    if diag is None:
        return None

    # Cílový audit existuje — musí jít o známý neúplný stav (markery NULL + snaps).
    is_incomplete_shape = bool(diag.missing_markers) and diag.snapshot_count > 0
    if not is_incomplete_shape:
        # Markery doplněné / bez snaps — neřeší tato cesta.
        return None

    if not diag.eligible_for_confirmed_cleanup:
        detail = "\n".join(f"• {item}" for item in diag.ineligibility_reasons)
        raise IncompleteManualAuditCleanupError(
            "Aplikaci nelze spustit: neúplný audit id="
            f"{diag.audit_id} obsahuje business data nebo nesplňuje "
            "podmínky bezpečného odstranění.\n\n"
            f"{format_incomplete_audit_dialog_text(diag)}\n\n"
            f"Důvody:\n{detail}\n\n"
            "Obnovte data ze zálohy nebo kontaktujte podporu. "
            "Automatické mazání se neprovádí."
        )

    confirmed = False
    if auto_confirm is True:
        confirmed = True
    elif auto_confirm is False:
        confirmed = False
    elif interactive:
        confirmed = prompt_incomplete_manual_audit_cleanup(diag)
    else:
        confirmed = False

    if not confirmed:
        raise IncompleteManualAuditCleanupError(
            "Odstranění neúplného testovacího auditu bylo zrušeno. "
            "Aplikaci nelze spustit s nekonzistentními daty.\n\n"
            f"{format_incomplete_audit_dialog_text(diag)}"
        )

    result = delete_incomplete_manual_audit_atomically(
        TARGET_INCOMPLETE_MANUAL_AUDIT_ID,
        workspace_root=workspace_root,
        database_path=database_path,
        settings_path=settings_path,
        create_backup=True,
    )

    # Po odstranění ověř zbývající audity (guard nesmí problém jen ignorovat).
    report = assess_legacy_backfill_integrity()
    bad = [
        item
        for item in report.items
        if item.status == AUDIT_BACKFILL_STATUS_INCONSISTENT
    ]
    if bad:
        detail = "; ".join(f"id={item.audit_id}: {item.detail}" for item in bad)
        raise IncompleteManualAuditCleanupError(
            "Po odstranění testovacího auditu zůstaly neúplné audity:\n"
            f"{detail}"
        )
    return result
