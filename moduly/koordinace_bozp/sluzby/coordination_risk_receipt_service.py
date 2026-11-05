"""Ukládání následného převzetí rizik.

Nemění původní dohodu. Protokol si převzetí přečte při sestavení
jako samostatný odstavec přílohy B.
Při prvním uložení dokončí jen jednoznačně navázaný otevřený úkol.
"""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_RISK_RECEIPT,
    ENTITY_COORDINATION_RISK_SUBMISSION,
    RISK_RECEIPT_METHOD_PAPER,
    RISK_RECEIPT_METHODS,
)
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    coordination_attachment_service,
)
from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
    CoordinationRiskReceipt,
    CoordinationRiskReceiptHistory,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_risk_submission_repository import (
    CoordinationEmployerRiskSubmissionRepository,
)
from moduly.koordinace_bozp.repository.coordination_risk_receipt_repository import (
    CoordinationRiskReceiptRepository,
)
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service


class CoordinationRiskReceiptError(ValueError):
    pass


class CoordinationRiskReceiptService:
    def __init__(self) -> None:
        self.repository = CoordinationRiskReceiptRepository()
        self.employer_repository = CoordinationEmployerRepository()
        self.submission_repository = CoordinationEmployerRiskSubmissionRepository()

    def get_for_employer(
        self,
        coordination_employer_id: int,
    ) -> CoordinationRiskReceipt | None:
        return self.repository.get_for_employer(coordination_employer_id)

    def list_history(
        self,
        receipt_id: int,
    ) -> list[CoordinationRiskReceiptHistory]:
        return self.repository.list_history(receipt_id)

    def save_receipt(
        self,
        coordination_employer_id: int,
        *,
        received_on: date,
        receipt_method: str,
        storage_location: str = "",
        note: str = "",
        attachment_id: int | None = None,
    ) -> CoordinationRiskReceipt:
        """Uloží nebo opraví aktuální převzetí. Historii zapíše jen při změně."""
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationRiskReceiptError("Zaměstnavatel nebyl nalezen.")
        if employer.is_main:
            raise CoordinationRiskReceiptError(
                "Hlavní zaměstnavatel následné převzetí rizik nevyplňuje."
            )

        method = (receipt_method or "").strip()
        if method not in RISK_RECEIPT_METHODS:
            raise CoordinationRiskReceiptError("Neplatný způsob převzetí rizik.")
        if not isinstance(received_on, date) or isinstance(received_on, datetime):
            raise CoordinationRiskReceiptError(
                "Datum skutečného převzetí je povinné."
            )

        storage_location = (storage_location or "").strip()
        note = (note or "").strip()
        attachment_id = self._require_receipt_attachment(employer, attachment_id)
        if method == RISK_RECEIPT_METHOD_PAPER and not storage_location:
            raise CoordinationRiskReceiptError(
                "U listinného převzetí je povinné uvést místo uložení dokumentu."
            )

        existing = self.repository.get_for_employer(coordination_employer_id)
        if existing is None:
            now = datetime.now()
            receipt = CoordinationRiskReceipt(
                coordination_employer_id=coordination_employer_id,
                received_on=received_on,
                receipt_method=method,
                storage_location=storage_location,
                note=note,
                attachment_id=attachment_id,
                recorded_at=now,
                created_at=now,
                updated_at=now,
            )
            stored = self.repository.add(receipt)
            self._complete_linked_open_task(coordination_employer_id)
            return stored

        if not self._values_changed(
            existing,
            received_on=received_on,
            receipt_method=method,
            storage_location=storage_location,
            note=note,
            attachment_id=attachment_id,
        ):
            return existing

        history = CoordinationRiskReceiptHistory(
            receipt_id=existing.id,
            received_on_before=existing.received_on,
            received_on_after=received_on,
            receipt_method_before=existing.receipt_method or "",
            receipt_method_after=method,
            storage_location_before=existing.storage_location or "",
            storage_location_after=storage_location,
            note_before=existing.note or "",
            note_after=note,
            attachment_id_before=existing.attachment_id,
            attachment_id_after=attachment_id,
            changed_at=datetime.now(),
        )
        existing.received_on = received_on
        existing.receipt_method = method
        existing.storage_location = storage_location
        existing.note = note
        existing.attachment_id = attachment_id
        existing.updated_at = datetime.now()
        return self.repository.update_with_history(existing, history)

    def _values_changed(
        self,
        receipt: CoordinationRiskReceipt,
        *,
        received_on: date,
        receipt_method: str,
        storage_location: str,
        note: str,
        attachment_id: int | None,
    ) -> bool:
        return (
            receipt.received_on != received_on
            or (receipt.receipt_method or "") != receipt_method
            or (receipt.storage_location or "") != storage_location
            or (receipt.note or "") != note
            or receipt.attachment_id != attachment_id
        )

    def _complete_linked_open_task(self, coordination_employer_id: int) -> None:
        """Dokončí otevřený úkol jen podle vazby na předání, ne podle názvu.

        Platné ``submission.task_id`` má přednost a ostatní úkoly se nedotýkají.
        Bez platné vazby se dokončí jen jediný úkol zdroje. Při více úkolech
        zdroje se nedokončí žádný. Oprava převzetí sem nevede.
        """
        submission = self.submission_repository.get_for_employer(
            coordination_employer_id
        )
        if submission is None:
            return

        linked = self._task_linked_by_submission(submission)
        if linked is not None:
            if not linked.completed and not linked.canceled:
                task_service.mark_completed(linked.id)
            return

        related = self._tasks_for_submission(submission.id)
        open_tasks = [task for task in related if not task.completed]
        if len(related) == 1 and len(open_tasks) == 1:
            task_service.mark_completed(open_tasks[0].id)

    def _task_linked_by_submission(self, submission) -> Task | None:
        if not submission.task_id:
            return None
        task = task_service.get_task_by_id(submission.task_id)
        if not self._belongs_to_submission(task, submission.id):
            return None
        return task

    def _tasks_for_submission(self, submission_id: int) -> list[Task]:
        return [
            task
            for task in task_service.list_by_source(
                ENTITY_COORDINATION_RISK_SUBMISSION,
                submission_id,
            )
            if self._belongs_to_submission(task, submission_id) and not task.canceled
        ]

    def _belongs_to_submission(self, task: Task | None, submission_id: int) -> bool:
        if task is None:
            return False
        return (
            task.source_module == ENTITY_COORDINATION_RISK_SUBMISSION
            and task.source_record_id == submission_id
        )

    def _require_receipt_attachment(self, employer, attachment_id: int | None) -> int | None:
        """Příloha převzetí musí být typu risk_receipt a patřit stejnému dodavateli."""
        if attachment_id is None:
            return None
        value = int(attachment_id)
        if value <= 0:
            raise CoordinationRiskReceiptError("Neplatná příloha.")
        attachment = coordination_attachment_service.get_by_id(value)
        if (
            attachment is None
            or attachment.attachment_type != ATTACHMENT_TYPE_RISK_RECEIPT
        ):
            raise CoordinationRiskReceiptError(
                "Lze přiřadit jen přílohu typu „Následné převzetí rizik“."
            )
        if attachment.coordination_employer_id != employer.id:
            raise CoordinationRiskReceiptError(
                "Příloha nepatří vybranému dodavateli."
            )
        if attachment.coordination_id != employer.coordination_id:
            raise CoordinationRiskReceiptError(
                "Příloha nepatří k této koordinaci."
            )
        return value


coordination_risk_receipt_service = CoordinationRiskReceiptService()
