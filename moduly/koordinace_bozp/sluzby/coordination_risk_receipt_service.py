"""Ukládání následného převzetí rizik (fáze B1).

Nemění původní dohodu, provozní stav předání, protokol ani úkoly.
"""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    RISK_RECEIPT_METHOD_PAPER,
    RISK_RECEIPT_METHODS,
)
from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
    CoordinationRiskReceipt,
    CoordinationRiskReceiptHistory,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_risk_receipt_repository import (
    CoordinationRiskReceiptRepository,
)


class CoordinationRiskReceiptError(ValueError):
    pass


class CoordinationRiskReceiptService:
    def __init__(self) -> None:
        self.repository = CoordinationRiskReceiptRepository()
        self.employer_repository = CoordinationEmployerRepository()

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
        attachment_id = self._normalize_attachment_id(attachment_id)
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
            return self.repository.add(receipt)

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

    def _normalize_attachment_id(self, attachment_id: int | None) -> int | None:
        if attachment_id is None:
            return None
        value = int(attachment_id)
        if value <= 0:
            raise CoordinationRiskReceiptError("Neplatná příloha.")
        return value


coordination_risk_receipt_service = CoordinationRiskReceiptService()
