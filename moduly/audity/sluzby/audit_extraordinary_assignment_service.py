"""AUDIT-EXTRAORDINARY-2: přiřazení mimořádných otázek do snapshotu auditu."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_AUDITY,
)
from core.shared.modely.control_result import ControlResult
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    EXTRAORDINARY_ASSERTION_ID_PREFIX,
    EXTRAORDINARY_CATEGORY_PROCESS_ID,
    EXTRAORDINARY_CATEGORY_PROCESS_NAME,
    EXTRAORDINARY_CATEGORY_SECTION_ID,
    EXTRAORDINARY_CATEGORY_SECTION_NAME,
    EXTRAORDINARY_INCOMPLETE_SEVERITY_FOR_AUDIT,
    EXTRAORDINARY_INCOMPLETE_VERIFICATION_TYPE_FOR_AUDIT,
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
    EXTRAORDINARY_SNAPSHOT_ORDER_BASE,
    EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
    EXTRAORDINARY_TARGET_STATUS_PENDING,
    EXTRAORDINARY_TARGET_STATUS_VERIFIED,
    extraordinary_assertion_id,
    parse_extraordinary_question_id,
)
from moduly.audity.modely.audit_extraordinary_question import (
    AuditExtraordinaryQuestion,
    AuditExtraordinaryQuestionTarget,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    is_auditable_workplace_id,
)
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    AuditExtraordinaryError,
    derive_question_status,
    require_valid_severity,
    require_valid_verification_type,
)
from moduly.audity.sluzby.audit_question_snapshot_service import (
    AuditQuestionSnapshotDraft,
)


@dataclass(frozen=True)
class PendingExtraordinaryAssignment:
    question: AuditExtraordinaryQuestion
    target: AuditExtraordinaryQuestionTarget


class AuditExtraordinaryAssignmentService:
    def list_pending_for_workplace(
        self,
        session: Session,
        workplace_id: int,
    ) -> list[PendingExtraordinaryAssignment]:
        """Pending cíle aktivních otázek pro provoz (včetně neúplné závažnosti)."""
        rows = list(
            session.execute(
                select(AuditExtraordinaryQuestion, AuditExtraordinaryQuestionTarget)
                .join(
                    AuditExtraordinaryQuestionTarget,
                    AuditExtraordinaryQuestionTarget.question_id
                    == AuditExtraordinaryQuestion.id,
                )
                .where(
                    AuditExtraordinaryQuestionTarget.workplace_id == int(workplace_id),
                    AuditExtraordinaryQuestionTarget.status
                    == EXTRAORDINARY_TARGET_STATUS_PENDING,
                    AuditExtraordinaryQuestion.status
                    == EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
                )
                .order_by(
                    AuditExtraordinaryQuestion.id,
                    AuditExtraordinaryQuestionTarget.id,
                )
            ).all()
        )
        return [
            PendingExtraordinaryAssignment(question=question, target=target)
            for question, target in rows
        ]

    def require_assignable_for_workplace(
        self,
        session: Session,
        workplace_id: int,
    ) -> list[PendingExtraordinaryAssignment]:
        """Vrátí přiřaditelné pending cíle; bez platné závažnosti/typu ověření chyba."""
        if not is_auditable_workplace_id(workplace_id):
            return []
        pending = self.list_pending_for_workplace(session, workplace_id)
        assignable: list[PendingExtraordinaryAssignment] = []
        for item in pending:
            text = str(item.question.question_text or "").strip() or "—"
            preview = text if len(text) <= 80 else f"{text[:77]}…"
            severity = str(item.question.severity or "").strip()
            if not severity:
                raise AuditExtraordinaryError(
                    EXTRAORDINARY_INCOMPLETE_SEVERITY_FOR_AUDIT.format(
                        text=preview,
                        question_id=int(item.question.id),
                    )
                )
            require_valid_severity(severity)
            verification = str(
                getattr(item.question, "verification_type", None) or ""
            ).strip()
            if not verification:
                raise AuditExtraordinaryError(
                    EXTRAORDINARY_INCOMPLETE_VERIFICATION_TYPE_FOR_AUDIT.format(
                        text=preview,
                        question_id=int(item.question.id),
                    )
                )
            try:
                require_valid_verification_type(verification)
            except AuditExtraordinaryError as exc:
                raise AuditExtraordinaryError(
                    EXTRAORDINARY_INCOMPLETE_VERIFICATION_TYPE_FOR_AUDIT.format(
                        text=preview,
                        question_id=int(item.question.id),
                    )
                ) from exc
            assignable.append(item)
        return assignable

    def build_snapshot_drafts(
        self,
        assignments: list[PendingExtraordinaryAssignment],
        *,
        audit_id: int,
        display_order_start: int = EXTRAORDINARY_SNAPSHOT_ORDER_BASE,
    ) -> list[AuditQuestionSnapshotDraft]:
        drafts: list[AuditQuestionSnapshotDraft] = []
        order = int(display_order_start)
        for item in assignments:
            question = item.question
            severity = require_valid_severity(question.severity)
            verification_type = require_valid_verification_type(
                getattr(question, "verification_type", None)
            )
            process_id = str(question.process_id or "").strip()
            process_name = str(question.process_name or "").strip()
            if process_id:
                resolved_process_id = process_id
                resolved_process_name = process_name or process_id
            else:
                resolved_process_id = EXTRAORDINARY_CATEGORY_PROCESS_ID
                resolved_process_name = EXTRAORDINARY_CATEGORY_PROCESS_NAME
            drafts.append(
                AuditQuestionSnapshotDraft(
                    audit_id=int(audit_id),
                    process_id=resolved_process_id,
                    process_name=resolved_process_name,
                    section_id=EXTRAORDINARY_CATEGORY_SECTION_ID,
                    section_name=EXTRAORDINARY_CATEGORY_SECTION_NAME,
                    assertion_id=extraordinary_assertion_id(int(question.id)),
                    assertion_text=str(question.question_text or "").strip(),
                    verification_type=verification_type,
                    severity=severity,
                    question_kind=AUDIT_QUESTION_KIND_EXTRAORDINARY,
                    display_order=order,
                )
            )
            order += 1
        return drafts

    def mark_assigned(
        self,
        session: Session,
        assignments: list[PendingExtraordinaryAssignment],
        *,
        audit_id: int,
        when: datetime | None = None,
    ) -> None:
        now = when or datetime.now()
        question_ids: set[int] = set()
        for item in assignments:
            target = session.get(
                AuditExtraordinaryQuestionTarget, int(item.target.id)
            )
            if target is None:
                continue
            if target.status != EXTRAORDINARY_TARGET_STATUS_PENDING:
                raise AuditExtraordinaryError(
                    f"Cíl id={target.id} už není ve stavu pending."
                )
            target.status = EXTRAORDINARY_TARGET_STATUS_ASSIGNED
            target.assigned_audit_id = int(audit_id)
            target.updated_at = now
            question_ids.add(int(target.question_id))
        self._refresh_question_statuses(session, question_ids, when=now)

    def finalize_for_completed_audit(
        self,
        session: Session,
        audit_id: int,
        *,
        when: datetime | None = None,
    ) -> None:
        """Vyhodnocené → verified; nevyhodnocené → pending (pro příští audit)."""
        now = when or datetime.now()
        targets = list(
            session.scalars(
                select(AuditExtraordinaryQuestionTarget).where(
                    AuditExtraordinaryQuestionTarget.assigned_audit_id == int(audit_id),
                    AuditExtraordinaryQuestionTarget.status
                    == EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
                )
            )
        )
        if not targets:
            return

        results = list(
            session.scalars(
                select(ControlResult).where(
                    ControlResult.entity_type == ENTITY_AUDITY,
                    ControlResult.entity_id == int(audit_id),
                )
            )
        )
        evaluated_question_ids: set[int] = set()
        for result in results:
            question_id = parse_extraordinary_question_id(
                str(result.source_control_point_id or "")
            )
            if question_id is None:
                continue
            value = str(result.result or "").strip() or CONTROL_RESULT_NEKONTROLOVANO
            if value == CONTROL_RESULT_NEKONTROLOVANO:
                continue
            evaluated_question_ids.add(question_id)

        question_ids: set[int] = set()
        for target in targets:
            question_ids.add(int(target.question_id))
            if int(target.question_id) in evaluated_question_ids:
                target.status = EXTRAORDINARY_TARGET_STATUS_VERIFIED
                target.verified_audit_id = int(audit_id)
                target.verified_at = now
                target.updated_at = now
            else:
                target.status = EXTRAORDINARY_TARGET_STATUS_PENDING
                target.assigned_audit_id = None
                target.updated_at = now
        self._refresh_question_statuses(session, question_ids, when=now)

    def release_unverified_for_audit(
        self,
        session: Session,
        audit_id: int,
        *,
        when: datetime | None = None,
    ) -> None:
        """Vrátí assigned (neověřené) cíle auditu do pending — zrušení/smazání."""
        now = when or datetime.now()
        targets = list(
            session.scalars(
                select(AuditExtraordinaryQuestionTarget).where(
                    AuditExtraordinaryQuestionTarget.assigned_audit_id == int(audit_id),
                    AuditExtraordinaryQuestionTarget.status
                    == EXTRAORDINARY_TARGET_STATUS_ASSIGNED,
                )
            )
        )
        if not targets:
            return
        question_ids: set[int] = set()
        for target in targets:
            target.status = EXTRAORDINARY_TARGET_STATUS_PENDING
            target.assigned_audit_id = None
            target.updated_at = now
            question_ids.add(int(target.question_id))
        self._refresh_question_statuses(session, question_ids, when=now)

    def _refresh_question_statuses(
        self,
        session: Session,
        question_ids: set[int],
        *,
        when: datetime,
    ) -> None:
        for question_id in question_ids:
            question = session.get(AuditExtraordinaryQuestion, int(question_id))
            if question is None:
                continue
            statuses = list(
                session.scalars(
                    select(AuditExtraordinaryQuestionTarget.status).where(
                        AuditExtraordinaryQuestionTarget.question_id == int(question_id)
                    )
                )
            )
            question.status = derive_question_status(statuses)
            question.updated_at = when


audit_extraordinary_assignment_service = AuditExtraordinaryAssignmentService()

# Re-export for callers that only need the prefix constant.
__all__ = [
    "EXTRAORDINARY_ASSERTION_ID_PREFIX",
    "AuditExtraordinaryAssignmentService",
    "PendingExtraordinaryAssignment",
    "audit_extraordinary_assignment_service",
]
