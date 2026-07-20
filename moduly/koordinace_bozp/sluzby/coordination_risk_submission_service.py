"""Služba předání rizik dodavatelů (COORD-006 / UX-COORD-13)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    ENTITY_COORDINATION_RISK_SUBMISSION,
    RISK_HANDOVER_STATUS_MAIN,
    RISK_HANDOVER_STATUS_UNSET,
    RISK_SUBMISSION_COMPLETED_STATUSES,
    RISK_SUBMISSION_PENDING_STATUSES,
    RISK_SUBMISSION_STATUS_LABELS,
    RISK_SUBMISSION_STATUS_WILL_EMAIL,
    RISK_SUBMISSION_STATUS_WILL_PAPER,
    RISK_SUBMISSION_STATUSES,
)
from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
    CoordinationEmployerRiskSubmission,
    CoordinationRiskSubmissionHistory,
)
from moduly.koordinace_bozp.repository.coordination_attachment_repository import (
    CoordinationAttachmentRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_risk_submission_repository import (
    CoordinationEmployerRiskSubmissionRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    employer_short_label,
)
from moduly.ukoly.sluzby.task_service import task_service


class CoordinationRiskSubmissionError(ValueError):
    pass


class CoordinationRiskSubmissionService:
    def __init__(self) -> None:
        self.repository = CoordinationEmployerRiskSubmissionRepository()
        self.employer_repository = CoordinationEmployerRepository()
        self.attachment_repository = CoordinationAttachmentRepository()

    def get_for_employer(
        self,
        coordination_employer_id: int,
    ) -> CoordinationEmployerRiskSubmission | None:
        return self.repository.get_for_employer(coordination_employer_id)

    def list_history(
        self,
        submission_id: int,
    ) -> list[CoordinationRiskSubmissionHistory]:
        return self.repository.list_history(submission_id)

    def save_submission(
        self,
        coordination_employer_id: int,
        *,
        submission_method: str,
        submission_date: date | None = None,
        document_reference: str = "",
        expected_email: str = "",
        risks_text: str = "",
        note: str = "",
    ) -> CoordinationEmployerRiskSubmission:
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationRiskSubmissionError("Zaměstnavatel nebyl nalezen.")
        if employer.is_main:
            raise CoordinationRiskSubmissionError(
                "Hlavní zaměstnavatel vlastní předání dodavatelských rizik nevyplňuje."
            )
        status = (submission_method or "").strip()
        if status not in RISK_SUBMISSION_STATUSES:
            raise CoordinationRiskSubmissionError("Neplatný stav předání rizik.")

        document_reference = (document_reference or "").strip()
        expected_email = (expected_email or "").strip()
        risks_text = (risks_text or "").strip()
        note = (note or "").strip()
        self._validate_fields_for_status(
            status,
            submission_date=submission_date,
            document_reference=document_reference,
            expected_email=expected_email,
            risks_text=risks_text,
        )

        existing = self.repository.get_for_employer(coordination_employer_id)
        previous_status = (
            existing.submission_method if existing is not None else ""
        )

        if existing is None:
            submission = CoordinationEmployerRiskSubmission(
                coordination_employer_id=coordination_employer_id,
                submission_method=status,
                submission_date=submission_date,
                document_reference=document_reference,
                expected_email=expected_email,
                risks_text=risks_text,
                note=note,
                active=True,
            )
            submission = self.repository.add(submission)
            self.repository.add_history(
                CoordinationRiskSubmissionHistory(
                    submission_id=submission.id,
                    from_status="",
                    to_status=status,
                    submission_date=submission_date,
                    document_reference=document_reference,
                    expected_email=expected_email,
                    risks_text=risks_text,
                    note=note,
                )
            )
        else:
            if previous_status != status:
                self.repository.add_history(
                    CoordinationRiskSubmissionHistory(
                        submission_id=existing.id,
                        from_status=previous_status or "",
                        to_status=status,
                        submission_date=existing.submission_date,
                        document_reference=existing.document_reference or "",
                        expected_email=existing.expected_email or "",
                        risks_text=existing.risks_text or "",
                        note=existing.note or "",
                    )
                )
            existing.submission_method = status
            existing.submission_date = submission_date
            existing.document_reference = document_reference
            existing.expected_email = expected_email
            existing.risks_text = risks_text
            existing.note = note
            existing.active = True
            existing.updated_at = datetime.now()
            submission = self.repository.update(existing)

        if status in RISK_SUBMISSION_PENDING_STATUSES:
            submission = self._ensure_follow_up_task(submission, employer)
        return submission

    def handover_status(self, coordination_employer_id: int) -> str:
        """Stav pro přehled a protokol – konečný stav předání (bez interních úkolů)."""
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            return RISK_HANDOVER_STATUS_UNSET
        if employer.is_main:
            return RISK_HANDOVER_STATUS_MAIN

        submission = self.repository.get_for_employer(coordination_employer_id)
        if submission is None:
            return RISK_HANDOVER_STATUS_UNSET
        status = submission.submission_method or ""
        if status in RISK_SUBMISSION_STATUSES:
            return status
        return RISK_HANDOVER_STATUS_UNSET

    def handover_status_label(self, coordination_employer_id: int) -> str:
        status = self.handover_status(coordination_employer_id)
        from moduly.koordinace_bozp.constants import RISK_HANDOVER_STATUS_LABELS

        return RISK_HANDOVER_STATUS_LABELS.get(status, status)

    def is_pending_status(self, status: str | None) -> bool:
        return (status or "") in RISK_SUBMISSION_PENDING_STATUSES

    def is_completed_status(self, status: str | None) -> bool:
        return (status or "") in RISK_SUBMISSION_COMPLETED_STATUSES

    def _validate_fields_for_status(
        self,
        status: str,
        *,
        submission_date: date | None,
        document_reference: str,
        expected_email: str,
        risks_text: str,
    ) -> None:
        if status == RISK_SUBMISSION_STATUS_WILL_EMAIL:
            if submission_date is None:
                raise CoordinationRiskSubmissionError(
                    "Termín doručení je povinný."
                )
            if not expected_email:
                raise CoordinationRiskSubmissionError(
                    "Očekávaná e-mailová adresa je povinná."
                )
        elif status == RISK_SUBMISSION_STATUS_WILL_PAPER:
            if submission_date is None:
                raise CoordinationRiskSubmissionError(
                    "Termín předání je povinný."
                )

    def _ensure_follow_up_task(self, submission, employer):
        short = employer_short_label(employer)
        if short.endswith(" (neaktivní)"):
            short = short[: -len(" (neaktivní)")]
        title = f"Předání rizik dodavatele {short}".strip()
        description = self._follow_up_task_description(submission, employer, short)

        open_task = None
        if submission.task_id:
            open_task = task_service.get_task_by_id(submission.task_id)
            if open_task is not None and open_task.completed:
                open_task = None
        if open_task is None:
            open_task = task_service.repository.find_open_by_source(
                source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
                source_record_id=submission.id,
            )

        if open_task is not None:
            task_service.update_task(
                open_task.id,
                title=title[:200],
                description=description,
                priority=open_task.priority or "Normální",
                due_date=submission.submission_date,
                responsible_person_id=open_task.responsible_person_id,
                workplace_id=open_task.workplace_id,
                completed=False,
                note=open_task.note or "",
                requires_verification=False,
            )
            if submission.task_id != open_task.id:
                submission.task_id = open_task.id
                submission.updated_at = datetime.now()
                return self.repository.update(submission)
            return submission

        task = task_service.create_task(
            title=title[:200],
            description=description,
            due_date=submission.submission_date,
            source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
            source_record_id=submission.id,
            requires_verification=False,
        )
        submission.task_id = task.id
        submission.updated_at = datetime.now()
        return self.repository.update(submission)

    def _follow_up_task_description(self, submission, employer, short: str) -> str:
        description_parts = [
            "Očekává se předání rizik dodavatele.",
            "",
            f"Dodavatel: {employer.company_name or short}",
        ]
        if submission.submission_method == RISK_SUBMISSION_STATUS_WILL_EMAIL:
            description_parts.append(
                f"Očekávaný e-mail: {submission.expected_email or '—'}"
            )
        if submission.note:
            description_parts.extend(["", f"Poznámka: {submission.note}"])
        description_parts.extend(
            [
                "",
                "Po obdržení rizik otevřete záznam v koordinaci, připojte dokument "
                "a změňte stav předání.",
            ]
        )
        return "\n".join(description_parts)


coordination_risk_submission_service = CoordinationRiskSubmissionService()
