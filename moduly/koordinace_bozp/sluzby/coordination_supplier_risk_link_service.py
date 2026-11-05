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


class CoordinationSupplierRiskLinkError(ValueError):
    pass


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
