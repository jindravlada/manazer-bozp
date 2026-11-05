"""Potvrzení dokumentů z katalogu pro konkrétního dodavatele v koordinaci.

Vyhledání ani prohlížení nic nezakládá. Vazba vznikne jen po výslovném
odsouhlasení a ukládá odkaz na existující dokument, ne kopii souboru.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from moduly.koordinace_bozp.repository.coordination_supplier_risk_link_repository import (
    CoordinationSupplierRiskLinkRepository,
    StoredCatalogLink,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
    SUPPLIER_CATALOG_MATCH_AMBIGUOUS,
    SUPPLIER_CATALOG_MATCH_INVALID,
    SUPPLIER_CATALOG_MATCH_NONE,
    SUPPLIER_CATALOG_MATCH_ONE,
    SupplierRiskDocumentRow,
    supplier_risk_service,
)

SUPPLIER_APPROVAL_REQUIRED_MESSAGE = (
    "Bez odsouhlasení dodavatele se vazby neuloží."
)
CATALOG_ASSIGNMENT_REFUSED_MESSAGE = "Dokumenty z katalogu nelze přiřadit."
CATALOG_DOCUMENT_MISMATCH_MESSAGE = (
    "Vybraný dokument nepatří k dodavateli podle IČO."
)
CATALOG_SELECTION_EMPTY_MESSAGE = "Nebyl vybrán žádný dokument."
CATALOG_REGISTRATION_REGISTERED = "registered"
CATALOG_REGISTRATION_ALREADY = "already"
CATALOG_REGISTRATION_SKIPPED = "skipped"
CATALOG_REGISTRATION_FAILED_MESSAGE = (
    "Příloha koordinace byla uložena.\n"
    "Zápis do katalogu Rizika dodavatelů se nepodařil.\n\n"
    "Dokument lze do katalogu doplnit ručně."
)


class CoordinationSupplierRiskLinkError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogRegistrationResult:
    """Výsledek automatického zápisu přílohy koordinace do katalogu."""

    status: str
    document_id: int | None = None
    company_id: int | None = None


@dataclass(frozen=True)
class CatalogDocumentOffer:
    """Nabídka dokumentů. Prázdný seznam znamená, že se nic nepřiřazuje."""

    status: str
    normalized_ico: str | None
    company_id: int | None
    documents: tuple[SupplierRiskDocumentRow, ...]


class CoordinationSupplierRiskLinkService:
    def __init__(self) -> None:
        self.repository = CoordinationSupplierRiskLinkRepository()

    def offer_for_employer(self, coordination_employer_id: int) -> CatalogDocumentOffer:
        """Sestaví nabídku podle IČO. Žádný záznam nezakládá ani nemění."""
        employer = coordination_employer_service.get_by_id(coordination_employer_id)
        if employer is None or employer.is_main:
            return CatalogDocumentOffer(
                status="invalid",
                normalized_ico=None,
                company_id=None,
                documents=(),
            )
        match = supplier_risk_service.find_catalog_company_by_ico(employer.ico)
        documents: tuple[SupplierRiskDocumentRow, ...] = ()
        if match.status == SUPPLIER_CATALOG_MATCH_ONE and match.company_id is not None:
            documents = tuple(
                supplier_risk_service.list_company_documents(match.company_id)
            )
        return CatalogDocumentOffer(
            status=match.status,
            normalized_ico=match.normalized_ico,
            company_id=(
                match.company_id
                if match.status == SUPPLIER_CATALOG_MATCH_ONE
                else None
            ),
            documents=documents,
        )

    def list_for_employer(self, coordination_employer_id: int) -> list[StoredCatalogLink]:
        return self.repository.list_for_employer(coordination_employer_id)

    def confirm_documents(
        self,
        coordination_employer_id: int,
        document_ids: list[int],
        *,
        supplier_approved: bool,
    ) -> list[StoredCatalogLink]:
        """Uloží odkazy na vybrané dokumenty. Bez odsouhlasení nic nezapíše."""
        if not supplier_approved:
            raise CoordinationSupplierRiskLinkError(SUPPLIER_APPROVAL_REQUIRED_MESSAGE)
        unique_ids = _unique_ids(document_ids)
        if not unique_ids:
            raise CoordinationSupplierRiskLinkError(CATALOG_SELECTION_EMPTY_MESSAGE)
        allowed = self._allowed_document_ids(coordination_employer_id)
        if any(document_id not in allowed for document_id in unique_ids):
            raise CoordinationSupplierRiskLinkError(CATALOG_DOCUMENT_MISMATCH_MESSAGE)
        existing = {
            item.document_id
            for item in self.repository.list_for_employer(coordination_employer_id)
        }
        for document_id in unique_ids:
            if document_id in existing:
                continue
            try:
                self.repository.add(
                    coordination_employer_id=coordination_employer_id,
                    supplier_risk_document_id=document_id,
                )
            except IntegrityError:
                continue
            existing.add(document_id)
        return self.repository.list_for_employer(coordination_employer_id)

    def register_handed_attachment(
        self,
        coordination_employer_id: int,
        coordination_attachment_id: int,
    ) -> CatalogRegistrationResult:
        """Zaeviduje už uloženou přílohu koordinace v katalogu, bez druhé kopie souboru."""
        from moduly.koordinace_bozp.constants import (
            ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            RISK_SUBMISSION_COMPLETED_STATUSES,
        )
        from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
            coordination_attachment_service,
        )
        from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
            coordination_risk_submission_service,
        )

        employer = coordination_employer_service.get_by_id(coordination_employer_id)
        attachment = coordination_attachment_service.get_by_id(
            coordination_attachment_id
        )
        if (
            employer is None
            or attachment is None
            or attachment.coordination_employer_id != employer.id
        ):
            raise CoordinationSupplierRiskLinkError(CATALOG_REGISTRATION_FAILED_MESSAGE)
        if (
            employer.is_main
            or attachment.attachment_type != ATTACHMENT_TYPE_CONTRACTOR_RISKS
        ):
            return CatalogRegistrationResult(status=CATALOG_REGISTRATION_SKIPPED)

        existing = supplier_risk_service.repository.get_by_coordination_attachment(
            int(attachment.id)
        )
        if existing is not None:
            self._ensure_link(employer.id, int(existing.id))
            return CatalogRegistrationResult(
                status=CATALOG_REGISTRATION_ALREADY,
                document_id=int(existing.id),
                company_id=int(existing.company_id),
            )

        match = supplier_risk_service.find_catalog_company_by_ico(employer.ico)
        if match.status in {
            SUPPLIER_CATALOG_MATCH_INVALID,
            SUPPLIER_CATALOG_MATCH_AMBIGUOUS,
        }:
            return CatalogRegistrationResult(status=CATALOG_REGISTRATION_SKIPPED)

        created_company_id: int | None = None
        if match.status == SUPPLIER_CATALOG_MATCH_NONE:
            try:
                company = supplier_risk_service.create_company(
                    name=employer.company_name or "",
                    ico=employer.ico,
                )
            except Exception as exc:
                raise CoordinationSupplierRiskLinkError(
                    CATALOG_REGISTRATION_FAILED_MESSAGE
                ) from exc
            company_id = int(company.id)
            created_company_id = company_id
        elif match.status == SUPPLIER_CATALOG_MATCH_ONE and match.company_id is not None:
            company_id = int(match.company_id)
        else:
            return CatalogRegistrationResult(status=CATALOG_REGISTRATION_SKIPPED)

        received_on = _handover_received_on(
            coordination_risk_submission_service.get_for_employer(employer.id),
            RISK_SUBMISSION_COMPLETED_STATUSES,
        )
        try:
            document_id = _insert_catalog_document_and_link(
                company_id=company_id,
                coordination_employer_id=int(employer.id),
                coordination_attachment_id=int(attachment.id),
                received_on=received_on,
            )
        except IntegrityError:
            existing = supplier_risk_service.repository.get_by_coordination_attachment(
                int(attachment.id)
            )
            if existing is None:
                if created_company_id is not None:
                    supplier_risk_service.repository.delete_company_without_documents(
                        created_company_id
                    )
                raise CoordinationSupplierRiskLinkError(
                    CATALOG_REGISTRATION_FAILED_MESSAGE
                )
            self._ensure_link(int(employer.id), int(existing.id))
            return CatalogRegistrationResult(
                status=CATALOG_REGISTRATION_ALREADY,
                document_id=int(existing.id),
                company_id=int(existing.company_id),
            )
        except Exception as exc:
            if created_company_id is not None:
                supplier_risk_service.repository.delete_company_without_documents(
                    created_company_id
                )
            raise CoordinationSupplierRiskLinkError(
                CATALOG_REGISTRATION_FAILED_MESSAGE
            ) from exc
        return CatalogRegistrationResult(
            status=CATALOG_REGISTRATION_REGISTERED,
            document_id=document_id,
            company_id=company_id,
        )

    def _ensure_link(self, coordination_employer_id: int, document_id: int) -> None:
        linked = {
            item.document_id
            for item in self.repository.list_for_employer(coordination_employer_id)
        }
        if document_id in linked:
            return
        try:
            self.repository.add(
                coordination_employer_id=coordination_employer_id,
                supplier_risk_document_id=document_id,
            )
        except IntegrityError:
            return

    def remove_documents(
        self,
        coordination_employer_id: int,
        document_ids: list[int],
    ) -> None:
        """Zruší vazby jen u tohoto dodavatele. Dokument v katalogu zůstane."""
        self.repository.delete_for_employer(
            coordination_employer_id,
            _unique_ids(document_ids),
        )

    def _allowed_document_ids(self, coordination_employer_id: int) -> set[int]:
        offer = self.offer_for_employer(coordination_employer_id)
        if offer.status != SUPPLIER_CATALOG_MATCH_ONE or offer.company_id is None:
            raise CoordinationSupplierRiskLinkError(CATALOG_ASSIGNMENT_REFUSED_MESSAGE)
        return {int(document.id) for document in offer.documents}


def _handover_received_on(submission, completed_statuses) -> object:
    """Datum převzetí jen ze skutečně dokončeného předání. Termín plánu se nepoužije."""
    if submission is None:
        return None
    if (submission.submission_method or "") not in completed_statuses:
        return None
    return submission.submission_date


def _insert_catalog_document_and_link(
    *,
    company_id: int,
    coordination_employer_id: int,
    coordination_attachment_id: int,
    received_on,
) -> int:
    from datetime import datetime

    from core.database.session import transaction
    from moduly.koordinace_bozp.modely.coordination_supplier_risk_link import (
        CoordinationSupplierRiskLink,
    )
    from moduly.rizeni_rizik.modely.supplier_risk import SupplierRiskDocument

    now = datetime.now()
    with transaction() as session:
        document = SupplierRiskDocument(
            company_id=company_id,
            received_on=received_on,
            prepared_on=None,
            note="",
            attachment_id=None,
            coordination_attachment_id=coordination_attachment_id,
            created_at=now,
            updated_at=now,
        )
        session.add(document)
        session.flush()
        session.add(
            CoordinationSupplierRiskLink(
                coordination_employer_id=coordination_employer_id,
                supplier_risk_document_id=document.id,
                created_at=now,
            )
        )
        session.flush()
        return int(document.id)


def _unique_ids(document_ids: list[int]) -> list[int]:
    unique: list[int] = []
    seen: set[int] = set()
    for raw in document_ids:
        value = int(raw)
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


coordination_supplier_risk_link_service = CoordinationSupplierRiskLinkService()
