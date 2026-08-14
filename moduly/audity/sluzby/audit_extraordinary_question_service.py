"""Služba evidence mimořádných otázek (AUDIT-EXTRAORDINARY-1/2).

Evidence + pending cíle; přiřazení do auditu řeší assignment service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.constants import (
    AUDITABLE_WORKPLACE_REQUIRED_MESSAGE,
    CONTROL_POINT_SEVERITY_KRITICKA,
    CONTROL_POINT_SEVERITY_NIZKA,
    CONTROL_POINT_SEVERITY_STREDNI,
    CONTROL_POINT_SEVERITY_VYSOKA,
    EXTRAORDINARY_CANCEL_BLOCKED,
    EXTRAORDINARY_DUPLICATE_TARGET,
    EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED,
    EXTRAORDINARY_PROCESS_NONE_LABEL,
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
    EXTRAORDINARY_QUESTION_STATUS_CANCELLED,
    EXTRAORDINARY_QUESTION_STATUS_COMPLETED,
    EXTRAORDINARY_QUESTION_TEXT_REQUIRED,
    EXTRAORDINARY_SEVERITY_REQUIRED,
    EXTRAORDINARY_SYSTEM_WORKPLACE_MARK,
    EXTRAORDINARY_TARGET_LOCKED,
    EXTRAORDINARY_TARGET_REQUIRED,
    EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
    EXTRAORDINARY_TARGET_STATUS_CANCELLED,
    EXTRAORDINARY_TARGET_STATUS_PENDING,
    EXTRAORDINARY_TARGET_STATUS_VERIFIED,
    EXTRAORDINARY_TEXT_LOCKED,
    EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL,
    EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED,
)
from moduly.audity.modely.audit_extraordinary_question import (
    AuditExtraordinaryQuestion,
    AuditExtraordinaryQuestionTarget,
)
from moduly.audity.repository.audit_extraordinary_question_repository import (
    AuditExtraordinaryQuestionRepository,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    is_auditable_workplace_id,
    list_auditable_workplaces,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.system_audit_workplace_service import (
    system_audit_workplace_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_LABELS,
    VERIFICATION_TYPE_TERRAIN,
)

_VALID_SEVERITIES = frozenset(
    {
        CONTROL_POINT_SEVERITY_KRITICKA,
        CONTROL_POINT_SEVERITY_VYSOKA,
        CONTROL_POINT_SEVERITY_STREDNI,
        CONTROL_POINT_SEVERITY_NIZKA,
    }
)

_VALID_VERIFICATION_TYPES = frozenset(
    {
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    }
)


class AuditExtraordinaryError(ValueError):
    """Validační / business chyba mimořádné otázky."""


def require_valid_severity(value) -> str:
    """Povinná závažnost z auditního číselníku (včetně Kritická)."""
    text = str(value or "").strip().lower()
    if not text:
        raise AuditExtraordinaryError(EXTRAORDINARY_SEVERITY_REQUIRED)
    if text not in _VALID_SEVERITIES:
        raise AuditExtraordinaryError(EXTRAORDINARY_SEVERITY_REQUIRED)
    return text


def require_valid_verification_type(value) -> str:
    """Povinný typ ověření Dokumentace/Terén (stávající interní hodnoty)."""
    text = str(value or "").strip().casefold()
    if not text:
        raise AuditExtraordinaryError(EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED)
    aliases = {
        VERIFICATION_TYPE_DOCUMENTATION: VERIFICATION_TYPE_DOCUMENTATION,
        "dokumentace": VERIFICATION_TYPE_DOCUMENTATION,
        "documentation": VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN: VERIFICATION_TYPE_TERRAIN,
        "teren": VERIFICATION_TYPE_TERRAIN,
        "terén": VERIFICATION_TYPE_TERRAIN,
        "terrain": VERIFICATION_TYPE_TERRAIN,
        "field": VERIFICATION_TYPE_TERRAIN,
    }
    normalized = aliases.get(text)
    if normalized is None or normalized not in _VALID_VERIFICATION_TYPES:
        raise AuditExtraordinaryError(EXTRAORDINARY_VERIFICATION_TYPE_REQUIRED)
    return normalized


def format_verification_type_label(value) -> str:
    """Popisek pro UI/export; prázdné/legacy → Neuvedeno (bez přepisu dat)."""
    text = str(value or "").strip()
    if not text:
        return EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL
    try:
        kind = require_valid_verification_type(text)
    except AuditExtraordinaryError:
        return EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL
    return VERIFICATION_TYPE_LABELS.get(kind, EXTRAORDINARY_VERIFICATION_TYPE_LEGACY_LABEL)


def resolve_optional_process(process_id: str | None) -> tuple[str | None, str]:
    """Vrátí (process_id, process_name); prázdné = kategorie Mimořádná ověření."""
    raw = str(process_id or "").strip()
    if not raw:
        return None, ""
    process = audit_knowledge_service.get_process_by_id(raw, ensure=True)
    if process is None or not bool(getattr(process, "aktivni", True)):
        raise AuditExtraordinaryError(
            f"Vybraný auditní proces „{raw}“ neexistuje nebo není aktivní."
        )
    name = str(getattr(process, "nazev", "") or "").strip() or raw
    return raw, name


@dataclass(frozen=True)
class WorkplaceChoice:
    workplace_id: int
    name: str
    is_system: bool
    is_auditable: bool = True

    @property
    def display_name(self) -> str:
        if self.is_system:
            return f"{self.name}{EXTRAORDINARY_SYSTEM_WORKPLACE_MARK}"
        return self.name


@dataclass(frozen=True)
class ExtraordinaryQuestionOverviewRow:
    question_id: int
    question_text: str
    assigned_by: str
    assigned_on: date | None
    status: str
    verification_type: str | None
    verification_type_label: str
    targets_total: int
    pending_count: int
    assigned_count: int
    verified_count: int
    cancelled_count: int


def derive_question_status(
    target_statuses: list[str] | tuple[str, ...],
) -> str:
    """Odvoz stav otázky z cílových stavů."""
    statuses = [str(item or "").strip() for item in target_statuses]
    if not statuses:
        return EXTRAORDINARY_QUESTION_STATUS_CANCELLED
    non_cancelled = [
        item
        for item in statuses
        if item != EXTRAORDINARY_TARGET_STATUS_CANCELLED
    ]
    if not non_cancelled:
        return EXTRAORDINARY_QUESTION_STATUS_CANCELLED
    if all(item == EXTRAORDINARY_TARGET_STATUS_VERIFIED for item in non_cancelled):
        return EXTRAORDINARY_QUESTION_STATUS_COMPLETED
    return EXTRAORDINARY_QUESTION_STATUS_ACTIVE


def is_target_locked(status: str) -> bool:
    return str(status or "").strip() in (
        EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
        EXTRAORDINARY_TARGET_STATUS_VERIFIED,
    )


class AuditExtraordinaryQuestionService:
    def __init__(self) -> None:
        self.repository = AuditExtraordinaryQuestionRepository()

    def list_selectable_workplaces(self) -> list[WorkplaceChoice]:
        """Pouze auditovatelné provozy; systémový jen pokud je auditovatelný."""
        system_id = system_audit_workplace_service.get_system_audit_workplace_id()
        choices: list[WorkplaceChoice] = []
        for workplace in list_auditable_workplaces():
            choices.append(
                WorkplaceChoice(
                    workplace_id=int(workplace.id),
                    name=str(workplace.name or "").strip() or f"#{workplace.id}",
                    is_system=(
                        system_id is not None and int(workplace.id) == int(system_id)
                    ),
                    is_auditable=True,
                )
            )
        return sorted(
            choices,
            key=lambda item: (not item.is_system, item.name.casefold(), item.workplace_id),
        )

    def _validate_auditable_workplace_ids(
        self,
        workplace_ids: list[int],
    ) -> None:
        for workplace_id in workplace_ids:
            if not is_auditable_workplace_id(workplace_id):
                raise AuditExtraordinaryError(AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)

    def list_overview_rows(self) -> list[ExtraordinaryQuestionOverviewRow]:
        questions = self.repository.list_questions()
        targets = self.repository.list_all_targets()
        by_question: dict[int, list[AuditExtraordinaryQuestionTarget]] = {}
        for target in targets:
            by_question.setdefault(int(target.question_id), []).append(target)

        rows: list[ExtraordinaryQuestionOverviewRow] = []
        for question in questions:
            q_targets = by_question.get(int(question.id), [])
            pending = sum(
                1
                for item in q_targets
                if item.status == EXTRAORDINARY_TARGET_STATUS_PENDING
            )
            assigned = sum(
                1
                for item in q_targets
                if item.status == EXTRAORDINARY_TARGET_STATUS_ASSIGNED
            )
            verified = sum(
                1
                for item in q_targets
                if item.status == EXTRAORDINARY_TARGET_STATUS_VERIFIED
            )
            cancelled = sum(
                1
                for item in q_targets
                if item.status == EXTRAORDINARY_TARGET_STATUS_CANCELLED
            )
            rows.append(
                ExtraordinaryQuestionOverviewRow(
                    question_id=int(question.id),
                    question_text=str(question.question_text or ""),
                    assigned_by=str(question.assigned_by or ""),
                    assigned_on=question.assigned_on,
                    status=str(question.status or ""),
                    verification_type=getattr(question, "verification_type", None),
                    verification_type_label=format_verification_type_label(
                        getattr(question, "verification_type", None)
                    ),
                    targets_total=len(q_targets),
                    pending_count=pending,
                    assigned_count=assigned,
                    verified_count=verified,
                    cancelled_count=cancelled,
                )
            )
        return rows

    def get_question(
        self,
        question_id: int,
    ) -> tuple[AuditExtraordinaryQuestion, list[AuditExtraordinaryQuestionTarget]]:
        question = self.repository.get_question(question_id)
        if question is None:
            raise AuditExtraordinaryError(f"Otázka id={question_id} neexistuje.")
        targets = self.repository.list_targets_for_question(question_id)
        return question, targets

    def is_question_text_locked(self, question_id: int) -> bool:
        targets = self.repository.list_targets_for_question(question_id)
        return any(is_target_locked(item.status) for item in targets)

    def list_process_choices(self) -> list[tuple[str | None, str]]:
        """Volby procesu: prázdná = Mimořádná ověření + aktivní procesy."""
        choices: list[tuple[str | None, str]] = [(None, EXTRAORDINARY_PROCESS_NONE_LABEL)]
        for process in audit_knowledge_service.get_processes(
            include_inactive=False, ensure=True
        ):
            process_id = str(getattr(process, "id", "") or "").strip()
            if not process_id:
                continue
            name = str(getattr(process, "nazev", "") or "").strip() or process_id
            choices.append((process_id, name))
        return choices

    def create_question(
        self,
        *,
        question_text: str,
        assigned_by: str = "",
        assigned_on: date | None = None,
        note: str = "",
        severity: str | None = None,
        process_id: str | None = None,
        verification_type: str | None = None,
        workplace_ids: list[int] | tuple[int, ...] | None = None,
        all_workplaces: bool = False,
    ) -> AuditExtraordinaryQuestion:
        text = str(question_text or "").strip()
        if not text:
            raise AuditExtraordinaryError(EXTRAORDINARY_QUESTION_TEXT_REQUIRED)
        severity_value = require_valid_severity(severity)
        verification_value = require_valid_verification_type(verification_type)
        resolved_process_id, resolved_process_name = resolve_optional_process(process_id)

        if all_workplaces:
            resolved_ids = [item.workplace_id for item in self.list_selectable_workplaces()]
        else:
            resolved_ids = [
                int(item)
                for item in (workplace_ids or [])
                if item is not None and int(item) > 0
            ]

        unique_ids = list(dict.fromkeys(resolved_ids))
        if not unique_ids:
            raise AuditExtraordinaryError(EXTRAORDINARY_TARGET_REQUIRED)
        if len(unique_ids) != len(resolved_ids):
            raise AuditExtraordinaryError(EXTRAORDINARY_DUPLICATE_TARGET)
        self._validate_auditable_workplace_ids(unique_ids)

        now = datetime.now()
        on_date = assigned_on or date.today()

        with get_session() as session:
            try:
                question = AuditExtraordinaryQuestion(
                    question_text=text,
                    assigned_by=str(assigned_by or "").strip(),
                    assigned_on=on_date,
                    note=str(note or "").strip(),
                    status=EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
                    process_id=resolved_process_id,
                    process_name=resolved_process_name,
                    severity=severity_value,
                    verification_type=verification_value,
                    created_at=now,
                    updated_at=now,
                )
                session.add(question)
                session.flush()

                for workplace_id in unique_ids:
                    session.add(
                        AuditExtraordinaryQuestionTarget(
                            question_id=question.id,
                            workplace_id=int(workplace_id),
                            status=EXTRAORDINARY_TARGET_STATUS_PENDING,
                            assigned_audit_id=None,
                            verified_audit_id=None,
                            verified_at=None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                session.commit()
                session.refresh(question)
                session.expunge(question)
                return question
            except Exception:
                session.rollback()
                raise

    def update_question(
        self,
        question_id: int,
        *,
        question_text: str | None = None,
        assigned_by: str | None = None,
        assigned_on: date | None = None,
        note: str | None = None,
        severity: str | None = None,
        process_id: str | None | object = ...,
        verification_type: str | None | object = ...,
        add_workplace_ids: list[int] | tuple[int, ...] | None = None,
        cancel_workplace_ids: list[int] | tuple[int, ...] | None = None,
        restore_workplace_ids: list[int] | tuple[int, ...] | None = None,
    ) -> AuditExtraordinaryQuestion:
        with get_session() as session:
            try:
                question = session.get(AuditExtraordinaryQuestion, int(question_id))
                if question is None:
                    raise AuditExtraordinaryError(
                        f"Otázka id={question_id} neexistuje."
                    )
                targets = list(
                    session.scalars(
                        select(AuditExtraordinaryQuestionTarget).where(
                            AuditExtraordinaryQuestionTarget.question_id
                            == int(question_id)
                        )
                    )
                )
                by_workplace = {int(item.workplace_id): item for item in targets}
                locked = any(is_target_locked(item.status) for item in targets)

                if question_text is not None:
                    text = str(question_text).strip()
                    if not text:
                        raise AuditExtraordinaryError(
                            EXTRAORDINARY_QUESTION_TEXT_REQUIRED
                        )
                    if locked and text != str(question.question_text or "").strip():
                        raise AuditExtraordinaryError(EXTRAORDINARY_TEXT_LOCKED)
                    question.question_text = text

                if assigned_by is not None:
                    question.assigned_by = str(assigned_by).strip()
                if assigned_on is not None:
                    question.assigned_on = assigned_on
                if note is not None:
                    question.note = str(note).strip()
                if severity is not None:
                    question.severity = require_valid_severity(severity)
                if verification_type is not ...:
                    question.verification_type = require_valid_verification_type(
                        verification_type
                    )
                if process_id is not ...:
                    resolved_process_id, resolved_process_name = resolve_optional_process(
                        None if process_id is None else str(process_id)
                    )
                    question.process_id = resolved_process_id
                    question.process_name = resolved_process_name

                now = datetime.now()

                for workplace_id in cancel_workplace_ids or ():
                    target = by_workplace.get(int(workplace_id))
                    if target is None:
                        continue
                    if is_target_locked(target.status):
                        raise AuditExtraordinaryError(EXTRAORDINARY_TARGET_LOCKED)
                    target.status = EXTRAORDINARY_TARGET_STATUS_CANCELLED
                    target.updated_at = now

                for workplace_id in restore_workplace_ids or ():
                    target = by_workplace.get(int(workplace_id))
                    if target is None:
                        continue
                    if is_target_locked(target.status):
                        raise AuditExtraordinaryError(EXTRAORDINARY_TARGET_LOCKED)
                    if not is_auditable_workplace_id(int(workplace_id)):
                        raise AuditExtraordinaryError(
                            EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED
                        )
                    target.status = EXTRAORDINARY_TARGET_STATUS_PENDING
                    target.updated_at = now

                add_ids = [
                    int(workplace_id)
                    for workplace_id in (add_workplace_ids or ())
                    if workplace_id is not None and int(workplace_id) > 0
                ]
                if add_ids:
                    self._validate_auditable_workplace_ids(add_ids)

                for workplace_id in add_ids:
                    wid = int(workplace_id)
                    existing = by_workplace.get(wid)
                    if existing is not None:
                        if existing.status == EXTRAORDINARY_TARGET_STATUS_CANCELLED:
                            if not is_auditable_workplace_id(wid):
                                raise AuditExtraordinaryError(
                                    EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED
                                )
                            existing.status = EXTRAORDINARY_TARGET_STATUS_PENDING
                            existing.updated_at = now
                            continue
                        raise AuditExtraordinaryError(EXTRAORDINARY_DUPLICATE_TARGET)
                    target = AuditExtraordinaryQuestionTarget(
                        question_id=int(question_id),
                        workplace_id=wid,
                        status=EXTRAORDINARY_TARGET_STATUS_PENDING,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(target)
                    by_workplace[wid] = target

                session.flush()
                refreshed = list(
                    session.scalars(
                        select(AuditExtraordinaryQuestionTarget).where(
                            AuditExtraordinaryQuestionTarget.question_id
                            == int(question_id)
                        )
                    )
                )
                if not refreshed:
                    raise AuditExtraordinaryError(EXTRAORDINARY_TARGET_REQUIRED)
                question.status = derive_question_status(
                    [item.status for item in refreshed]
                )
                question.updated_at = now
                session.commit()
                session.refresh(question)
                session.expunge(question)
                return question
            except Exception:
                session.rollback()
                raise

    def cancel_question(self, question_id: int) -> AuditExtraordinaryQuestion:
        with get_session() as session:
            try:
                question = session.get(AuditExtraordinaryQuestion, int(question_id))
                if question is None:
                    raise AuditExtraordinaryError(
                        f"Otázka id={question_id} neexistuje."
                    )
                targets = list(
                    session.scalars(
                        select(AuditExtraordinaryQuestionTarget).where(
                            AuditExtraordinaryQuestionTarget.question_id
                            == int(question_id)
                        )
                    )
                )
                if any(is_target_locked(item.status) for item in targets):
                    raise AuditExtraordinaryError(EXTRAORDINARY_CANCEL_BLOCKED)
                now = datetime.now()
                for target in targets:
                    target.status = EXTRAORDINARY_TARGET_STATUS_CANCELLED
                    target.updated_at = now
                question.status = EXTRAORDINARY_QUESTION_STATUS_CANCELLED
                question.updated_at = now
                session.commit()
                session.refresh(question)
                session.expunge(question)
                return question
            except Exception:
                session.rollback()
                raise

    def reactivate_question(self, question_id: int) -> AuditExtraordinaryQuestion:
        """Obnoví zrušenou otázku: cancelled cíle → pending, stav active."""
        with get_session() as session:
            try:
                question = session.get(AuditExtraordinaryQuestion, int(question_id))
                if question is None:
                    raise AuditExtraordinaryError(
                        f"Otázka id={question_id} neexistuje."
                    )
                targets = list(
                    session.scalars(
                        select(AuditExtraordinaryQuestionTarget).where(
                            AuditExtraordinaryQuestionTarget.question_id
                            == int(question_id)
                        )
                    )
                )
                now = datetime.now()
                for target in targets:
                    if target.status != EXTRAORDINARY_TARGET_STATUS_CANCELLED:
                        continue
                    if not is_auditable_workplace_id(int(target.workplace_id)):
                        continue
                    target.status = EXTRAORDINARY_TARGET_STATUS_PENDING
                    target.updated_at = now
                question.status = derive_question_status(
                    [item.status for item in targets]
                )
                question.updated_at = now
                session.commit()
                session.refresh(question)
                session.expunge(question)
                return question
            except Exception:
                session.rollback()
                raise

    def cancel_target(
        self,
        question_id: int,
        workplace_id: int,
    ) -> AuditExtraordinaryQuestionTarget:
        return self._set_target_status(
            question_id,
            workplace_id,
            EXTRAORDINARY_TARGET_STATUS_CANCELLED,
        )

    def restore_target(
        self,
        question_id: int,
        workplace_id: int,
    ) -> AuditExtraordinaryQuestionTarget:
        return self._set_target_status(
            question_id,
            workplace_id,
            EXTRAORDINARY_TARGET_STATUS_PENDING,
        )

    def _set_target_status(
        self,
        question_id: int,
        workplace_id: int,
        new_status: str,
    ) -> AuditExtraordinaryQuestionTarget:
        with get_session() as session:
            try:
                question = session.get(AuditExtraordinaryQuestion, int(question_id))
                if question is None:
                    raise AuditExtraordinaryError(
                        f"Otázka id={question_id} neexistuje."
                    )
                target = session.scalars(
                    select(AuditExtraordinaryQuestionTarget).where(
                        AuditExtraordinaryQuestionTarget.question_id == int(question_id),
                        AuditExtraordinaryQuestionTarget.workplace_id
                        == int(workplace_id),
                    )
                ).first()
                if target is None:
                    raise AuditExtraordinaryError(
                        f"Cíl workplace_id={workplace_id} neexistuje."
                    )
                if is_target_locked(target.status):
                    raise AuditExtraordinaryError(EXTRAORDINARY_TARGET_LOCKED)
                if (
                    new_status == EXTRAORDINARY_TARGET_STATUS_PENDING
                    and not is_auditable_workplace_id(int(workplace_id))
                ):
                    raise AuditExtraordinaryError(
                        EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED
                    )
                now = datetime.now()
                target.status = new_status
                target.updated_at = now
                session.flush()
                all_targets = list(
                    session.scalars(
                        select(AuditExtraordinaryQuestionTarget).where(
                            AuditExtraordinaryQuestionTarget.question_id
                            == int(question_id)
                        )
                    )
                )
                question.status = derive_question_status(
                    [item.status for item in all_targets]
                )
                question.updated_at = now
                session.commit()
                session.refresh(target)
                session.expunge(target)
                return target
            except Exception:
                session.rollback()
                raise


audit_extraordinary_question_service = AuditExtraordinaryQuestionService()
