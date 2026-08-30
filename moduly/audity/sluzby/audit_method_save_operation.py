"""AUDIT-METHOD-LONG-OPERATION-4B: čistá persistence editoru auditní metodiky.

Funkce ``persist_audit_method_save`` je nezávislá na Qt UI. Vstup i výstup
jsou běžné Python objekty (snapshot / výsledek). Worker nesmí dostat widget,
Qt model, dialog ani živou SQLAlchemy session z GUI vlákna.
"""

from __future__ import annotations

import threading
from copy import deepcopy
from dataclasses import dataclass

from core.widgets.long_operation_runner import LongOperationContext
from moduly.audity.sluzby.audit_knowledge_editor_service import (
    AssertionQuestionKindChange,
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.system_audit_workplace_service import (
    SystemAuditWorkplaceError,
    system_audit_workplace_service,
)

PHASE_PREPARE = "Připravuji změny…"
PHASE_VALIDATE = "Kontroluji auditní metodiku…"
PHASE_BACKUP = "Vytvářím bezpečnostní zálohu…"
PHASE_SAVE = "Ukládám auditní metodiku…"
PHASE_VERIFY = "Ověřuji uložená data…"
PHASE_RELOAD = "Obnovuji editor…"

AUDIT_METHOD_SAVE_RELOAD_FAILED_TEXT = (
    "Auditní metodika byla uložena, ale editor se nepodařilo obnovit.\n\n"
    "Zavřete editor a otevřete ho znovu. Neupravujte zobrazená data — "
    "nemusí odpovídat uloženému stavu."
)


class AuditMethodSaveError(Exception):
    """Uživatelská chyba persistence (validace, záloha, zápis, post-kontrola)."""


@dataclass(frozen=True)
class AuditMethodSaveSnapshot:
    """Hluboká čistá kopie pending změn — bez Qt a bez GUI session."""

    system_workplace_pending: bool
    system_workplace_id: int | None
    question_kind_changes: tuple[AssertionQuestionKindChange, ...]
    process_drafts: tuple[tuple[str, dict], ...]
    section_drafts: tuple[tuple[str, str, dict], ...]
    selected_process_id: str
    selected_section_id: str
    include_inactive: bool = True
    snapshot_thread_ident: int = 0

    def has_work(self) -> bool:
        return (
            self.system_workplace_pending
            or bool(self.question_kind_changes)
            or bool(self.process_drafts)
            or bool(self.section_drafts)
        )


@dataclass(frozen=True)
class AuditMethodSaveResult:
    """Čistá data pro GUI epilog. Bez Qt objektů."""

    saved_system_workplace: bool
    saved_question_kinds: int
    saved_process_ids: tuple[str, ...]
    saved_section_keys: tuple[tuple[str, str], ...]
    unclassified_count: int
    knowledge_tree: tuple[KnowledgeTreeNode, ...]
    pre_v2_created: bool
    selected_process_id: str
    selected_section_id: str
    worker_thread_ident: int


def _raise_if_errors(errors: list[str] | tuple[str, ...]) -> None:
    if errors:
        raise AuditMethodSaveError("\n".join(str(item) for item in errors))


def persist_audit_method_save(
    ctx: LongOperationContext,
    snapshot: AuditMethodSaveSnapshot,
) -> AuditMethodSaveResult:
    """Persistuje snapshot editoru. Volat z workeru, ne z GUI vlákna."""
    if not isinstance(snapshot, AuditMethodSaveSnapshot):
        raise TypeError(
            "persist_audit_method_save očekává AuditMethodSaveSnapshot, "
            f"dostáno {type(snapshot)!r}."
        )

    from moduly.audity.sluzby.audit_method_v2_backup_service import (
        AuditMethodV2BackupError,
        ensure_pre_v2_backup,
        pre_v2_backup_exists,
    )

    ctx.set_phase(PHASE_PREPARE, indeterminate=True, atomic=False)
    ctx.check_cancel()

    kind_changes = snapshot.question_kind_changes
    needs_validate = bool(
        kind_changes or snapshot.process_drafts or snapshot.section_drafts
    )
    if needs_validate:
        ctx.set_phase(PHASE_VALIDATE, indeterminate=True, atomic=False)
        if kind_changes:
            _normalized, kind_errors = (
                audit_knowledge_editor_service._normalize_question_kind_changes(
                    kind_changes
                )
            )
            _raise_if_errors(kind_errors)
            kind_changes = tuple(_normalized)
        for process_id, metadata in snapshot.process_drafts:
            if not str((metadata or {}).get("nazev") or "").strip():
                raise AuditMethodSaveError("Název procesu musí být vyplněn.")
        for _process_id, _section_id, metadata in snapshot.section_drafts:
            if not str((metadata or {}).get("nazev") or "").strip():
                raise AuditMethodSaveError(
                    "Název oblasti ověření musí být vyplněn."
                )
        ctx.check_cancel()

    needs_pre_v2 = (not pre_v2_backup_exists()) and (
        snapshot.system_workplace_pending or bool(kind_changes)
    )

    ctx.check_cancel()
    pre_v2_created = False
    if snapshot.has_work() or needs_pre_v2:
        if needs_pre_v2:
            ctx.set_phase(PHASE_BACKUP, indeterminate=True, atomic=True)
            try:
                backup_path = ensure_pre_v2_backup()
            except AuditMethodV2BackupError as exc:
                raise AuditMethodSaveError(str(exc)) from exc
            pre_v2_created = backup_path is not None
        else:
            ctx.set_phase(PHASE_SAVE, indeterminate=True, atomic=True)

        ctx.set_phase(PHASE_SAVE, indeterminate=True, atomic=True)
        write_steps = (
            (1 if snapshot.system_workplace_pending else 0)
            + (1 if kind_changes else 0)
            + len(snapshot.process_drafts)
            + len(snapshot.section_drafts)
        )
        if write_steps > 0:
            ctx.set_progress(0, write_steps)
        step = 0

        saved_workplace = False
        if snapshot.system_workplace_pending:
            try:
                system_audit_workplace_service.persist_saved_system_workplace_id(
                    snapshot.system_workplace_id
                )
            except (SystemAuditWorkplaceError, AuditMethodV2BackupError) as exc:
                raise AuditMethodSaveError(str(exc)) from exc
            saved_workplace = True
            step += 1
            ctx.set_progress(step, write_steps)

        saved_kinds = 0
        if kind_changes:
            errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
                kind_changes
            )
            _raise_if_errors(errors)
            saved_kinds = len(kind_changes)
            step += 1
            ctx.set_progress(step, write_steps)

        saved_process_ids: list[str] = []
        for process_id, metadata in snapshot.process_drafts:
            errors = audit_knowledge_editor_service.save_process_metadata(
                process_id,
                deepcopy(metadata),
            )
            _raise_if_errors(errors)
            saved_process_ids.append(process_id)
            step += 1
            ctx.set_progress(step, write_steps)

        saved_section_keys: list[tuple[str, str]] = []
        for process_id, section_id, metadata in snapshot.section_drafts:
            errors = audit_knowledge_editor_service.save_section_metadata(
                process_id,
                section_id,
                deepcopy(metadata),
                skip_legal_resolve=True,
            )
            _raise_if_errors(errors)
            saved_section_keys.append((process_id, section_id))
            step += 1
            ctx.set_progress(step, write_steps)
    else:
        saved_workplace = False
        saved_kinds = 0
        saved_process_ids = []
        saved_section_keys = []

    ctx.set_phase(PHASE_VERIFY, indeterminate=True, atomic=True)
    tree = tuple(
        audit_knowledge_service.get_knowledge_tree(
            include_inactive=snapshot.include_inactive,
            ensure=False,
        )
    )
    unclassified_count = audit_knowledge_service.count_unclassified_active_assertions(
        ensure=False,
        knowledge_tree=list(tree),
    )

    return AuditMethodSaveResult(
        saved_system_workplace=saved_workplace,
        saved_question_kinds=saved_kinds,
        saved_process_ids=tuple(saved_process_ids),
        saved_section_keys=tuple(saved_section_keys),
        unclassified_count=unclassified_count,
        knowledge_tree=tree,
        pre_v2_created=pre_v2_created,
        selected_process_id=snapshot.selected_process_id,
        selected_section_id=snapshot.selected_section_id,
        worker_thread_ident=threading.get_ident(),
    )
