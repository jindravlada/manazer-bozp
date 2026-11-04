"""Služba předání rizik dodavatelů (COORD-006 / UX-COORD-13)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUS_CLOSED,
    ENTITY_COORDINATION_RISK_SUBMISSION,
    RISK_HANDOVER_STATUS_LABELS,
    RISK_HANDOVER_STATUS_MAIN,
    RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED,
    RISK_HANDOVER_STATUS_UNSET,
    RISK_RECEIPT_METHOD_LABELS,
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


@dataclass(frozen=True)
class OperationalRiskHandover:
    """Provozní stav předání. Do protokolu se nepropisuje."""

    status: str
    label: str
    received_on: date | None = None
    receipt_method: str = ""
    receipt_method_label: str = ""


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
        return RISK_HANDOVER_STATUS_LABELS.get(status, status)

    def operational_handover(
        self,
        coordination_employer_id: int,
    ) -> OperationalRiskHandover:
        """Stav pro upozornění a přehled. Původní dohoda zůstává v ``handover_status``."""
        agreement_status = self.handover_status(coordination_employer_id)
        if agreement_status == RISK_HANDOVER_STATUS_MAIN:
            return self._operational_from_agreement(agreement_status)

        from moduly.koordinace_bozp.sluzby.coordination_risk_receipt_service import (
            coordination_risk_receipt_service,
        )

        receipt = coordination_risk_receipt_service.get_for_employer(
            coordination_employer_id
        )
        if receipt is None:
            return self._operational_from_agreement(agreement_status)

        method = receipt.receipt_method or ""
        return OperationalRiskHandover(
            status=RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED,
            label=RISK_HANDOVER_STATUS_LABELS[
                RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED
            ],
            received_on=receipt.received_on,
            receipt_method=method,
            receipt_method_label=RISK_RECEIPT_METHOD_LABELS.get(method, method),
        )

    def _operational_from_agreement(self, status: str) -> OperationalRiskHandover:
        return OperationalRiskHandover(
            status=status,
            label=RISK_HANDOVER_STATUS_LABELS.get(status, status),
        )

    def accepts_subsequent_risk_receipt(self, coordination_id: int) -> bool:
        """Uzavřená koordinace s plánovaným předáním nebo už uloženým převzetím."""
        from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
            bozp_coordination_service,
        )
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            normalize_coordination_status,
        )
        from moduly.koordinace_bozp.sluzby.coordination_risk_receipt_service import (
            coordination_risk_receipt_service,
        )

        coordination = bozp_coordination_service.get_by_id(coordination_id)
        if coordination is None:
            return False
        if (
            normalize_coordination_status(coordination.status)
            != BOZP_COORDINATION_STATUS_CLOSED
        ):
            return False
        for employer in self.employer_repository.list_for_coordination(
            coordination_id,
            include_inactive=True,
        ):
            if employer.is_main:
                continue
            if coordination_risk_receipt_service.get_for_employer(employer.id) is not None:
                return True
            if self.handover_status(employer.id) in RISK_SUBMISSION_PENDING_STATUSES:
                return True
        return False

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

        # Splněný úkol je pořád tentýž závazek. Nový vznikne jen bez navázaného úkolu.
        completed_task = self._completed_follow_up_task(submission)
        if completed_task is not None:
            if submission.task_id != completed_task.id:
                submission.task_id = completed_task.id
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

    def _completed_follow_up_task(self, submission):
        """Vrátí splněný úkol předání, pokud už k záznamu nějaký patří.

        Nejdřív přímá vazba ``task_id``, potom zdrojový modul a id předání.
        Úkol se neupravuje a další splněné duplicity se nemažou.
        """
        if submission.task_id:
            linked = task_service.get_task_by_id(submission.task_id)
            if linked is not None and linked.completed:
                return linked
        related = task_service.list_by_source(
            ENTITY_COORDINATION_RISK_SUBMISSION,
            submission.id,
        )
        completed = [task for task in related if task.completed]
        if not completed:
            return None
        return min(completed, key=lambda task: task.id)

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
