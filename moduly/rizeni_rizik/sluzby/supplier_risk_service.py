from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from core.export.open_export import open_local_file
from core.services.ares_service import ares_service
from core.services.attachment_service import attachment_service
from moduly.rizeni_rizik.constants import SUPPLIER_RISK_ENTITY_TYPE
from moduly.rizeni_rizik.modely.supplier_risk import (
    SupplierRiskCompany,
    SupplierRiskDocument,
)
from moduly.rizeni_rizik.repository.supplier_risk_repository import (
    SupplierRiskRepository,
)


class SupplierRiskError(ValueError):
    """Neplatná evidence rizik dodavatele."""


_KEEP_PREPARED_ON = object()


DUPLICATE_SUPPLIER_ICO_MESSAGE = "Firma s tímto IČO už je evidována."


@dataclass(frozen=True)
class SupplierRiskDocumentRow:
    id: int
    company_id: int
    company_name: str
    ico: str
    filename: str
    prepared_on: date | None
    received_on: date | None
    note: str
    attachment_id: int
    stored_path: str


@dataclass(frozen=True)
class SupplierRiskSaveResult:
    row: SupplierRiskDocumentRow
    reused_existing_company: bool


def normalize_supplier_ico(value: str | None) -> str | None:
    """Vrátí IČO jako osm číslic, nebo None když je pole prázdné."""
    raw = str(value or "")
    if not raw.strip():
        return None
    without_spaces = "".join(raw.split())
    if not without_spaces.isdigit():
        raise SupplierRiskError("IČO smí obsahovat pouze číslice.")
    if len(without_spaces) > 8:
        raise SupplierRiskError("IČO smí obsahovat nejvýše 8 číslic.")
    return without_spaces.zfill(8)


def _stored_ico(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _require_company_identity(name: str, ico: str | None) -> tuple[str, str]:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise SupplierRiskError("Název firmy je povinný.")
    normalized_ico = normalize_supplier_ico(ico)
    if not normalized_ico:
        raise SupplierRiskError("IČO je povinné.")
    return cleaned_name, normalized_ico


def supplier_risk_search_matches(*, company_name: str, ico: str, query: str) -> bool:
    text = (query or "").strip().lower()
    if not text:
        return True
    haystack = f"{company_name or ''} {ico or ''}".lower()
    return text in haystack


class SupplierRiskService:
    def __init__(self, repository: SupplierRiskRepository | None = None):
        self.repository = repository or SupplierRiskRepository()

    def list_companies(self) -> list[SupplierRiskCompany]:
        return self.repository.list_companies()

    def get_company(self, company_id: int) -> SupplierRiskCompany | None:
        return self.repository.get_company(company_id)

    def create_company(self, *, name: str, ico: str | None) -> SupplierRiskCompany:
        """Založí firmu bez dokumentu. Stejné IČO odmítne a nic nesloučí."""
        cleaned_name, normalized_ico = _require_company_identity(name, ico)
        if self.repository.get_by_ico(normalized_ico) is not None:
            raise SupplierRiskError(DUPLICATE_SUPPLIER_ICO_MESSAGE)
        try:
            return self.repository.add_company(
                SupplierRiskCompany(
                    name=cleaned_name,
                    ico=normalized_ico,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
        except IntegrityError as exc:
            raise SupplierRiskError(DUPLICATE_SUPPLIER_ICO_MESSAGE) from exc

    def update_company_identity(
        self,
        company_id: int,
        *,
        name: str,
        ico: str | None,
    ) -> SupplierRiskCompany:
        """Upraví název a IČO. Dokumenty zůstanou u této firmy."""
        cleaned_name, normalized_ico = _require_company_identity(name, ico)
        current = self.repository.get_company(company_id)
        if current is None:
            raise SupplierRiskError("Firma nebyla nalezena.")
        other = self.repository.get_by_ico(normalized_ico)
        if other is not None and other.id != current.id:
            raise SupplierRiskError(DUPLICATE_SUPPLIER_ICO_MESSAGE)
        if current.name == cleaned_name and _stored_ico(current.ico) == normalized_ico:
            return current
        current.name = cleaned_name
        current.ico = normalized_ico
        current.updated_at = datetime.now()
        try:
            return self.repository.update_company(current)
        except IntegrityError as exc:
            raise SupplierRiskError(DUPLICATE_SUPPLIER_ICO_MESSAGE) from exc

    def company_name_from_ares(self, ico: str | None) -> str:
        """Vrátí jen obchodní jméno. Při neúspěchu nic neukládá."""
        normalized = normalize_supplier_ico(ico)
        if not normalized:
            raise SupplierRiskError("Zadejte IČO.")
        try:
            data = ares_service.find_by_ico(normalized)
        except SupplierRiskError:
            raise
        except Exception as exc:
            raise SupplierRiskError("Nepodařilo se načíst data z ARES.") from exc
        name = str((data or {}).get("name") or "").strip()
        if not name:
            raise SupplierRiskError("Záznam nebyl nalezen.")
        return name

    def list_documents(self) -> list[SupplierRiskDocumentRow]:
        rows = []
        for document, company, attachment in self.repository.list_rows():
            rows.append(self._row(document, company, attachment))
        return rows

    def list_company_documents(self, company_id: int) -> list[SupplierRiskDocumentRow]:
        return [row for row in self.list_documents() if row.company_id == company_id]

    def add_company_document(
        self,
        company_id: int,
        *,
        received_on: date | None,
        note: str,
        source_path: str,
        prepared_on: date | None = None,
    ) -> SupplierRiskDocumentRow:
        """Přidá nový dokument. Původní záznamy ani jejich soubory nemění."""
        company = self.repository.get_company(company_id)
        if company is None:
            raise SupplierRiskError("Firma nebyla nalezena.")
        source = Path(source_path or "")
        if not source.is_file():
            raise SupplierRiskError("Dokument rizik je povinný.")
        document = self.repository.add_document(
            SupplierRiskDocument(
                company_id=company.id,
                received_on=received_on,
                prepared_on=prepared_on,
                note=(note or "").strip(),
                attachment_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        attachment = attachment_service.add_file(
            SUPPLIER_RISK_ENTITY_TYPE,
            document.id,
            str(source),
        )
        if attachment is None:
            self.repository.delete_document(document.id)
            raise SupplierRiskError("Dokument se nepodařilo uložit do úložiště příloh.")
        document.attachment_id = attachment.id
        document.updated_at = datetime.now()
        document = self.repository.update_document(document)
        return self._require_row(document.id)

    def update_document_details(
        self,
        document_id: int,
        *,
        received_on: date | None,
        note: str,
        prepared_on: date | None | object = _KEEP_PREPARED_ON,
    ) -> SupplierRiskDocumentRow:
        """Změní údaje dokumentu. Soubor ani firmu nemění a datum zpracování samo nedoplní."""
        document = self.repository.get_document(document_id)
        if document is None or not document.attachment_id:
            raise SupplierRiskError("Dokument nebyl nalezen.")
        document.received_on = received_on
        document.note = (note or "").strip()
        if prepared_on is not _KEEP_PREPARED_ON:
            document.prepared_on = prepared_on
        document.updated_at = datetime.now()
        self.repository.update_document(document)
        return self._require_row(document_id)

    def create_document(
        self,
        *,
        company_id: int | None,
        name: str,
        ico: str | None,
        received_on: date | None,
        note: str,
        source_path: str,
        prepared_on: date | None = None,
    ) -> SupplierRiskSaveResult:
        source = Path(source_path or "")
        if not source.is_file():
            raise SupplierRiskError("Dokument rizik je povinný.")
        company, reused = self._resolve_company(
            company_id=company_id,
            name=name,
            ico=ico,
        )
        document = self.repository.add_document(
            SupplierRiskDocument(
                company_id=company.id,
                received_on=received_on,
                prepared_on=prepared_on,
                note=(note or "").strip(),
                attachment_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        attachment = attachment_service.add_file(
            SUPPLIER_RISK_ENTITY_TYPE,
            document.id,
            str(source),
        )
        if attachment is None:
            self.repository.delete_document(document.id)
            raise SupplierRiskError("Dokument se nepodařilo uložit do úložiště příloh.")
        document.attachment_id = attachment.id
        document.updated_at = datetime.now()
        document = self.repository.update_document(document)
        return SupplierRiskSaveResult(
            row=self._require_row(document.id),
            reused_existing_company=reused,
        )

    def update_document(
        self,
        document_id: int,
        *,
        company_id: int | None,
        name: str,
        ico: str | None,
        received_on: date | None,
        note: str,
        prepared_on: date | None | object = _KEEP_PREPARED_ON,
    ) -> SupplierRiskSaveResult:
        document = self.repository.get_document(document_id)
        if document is None or not document.attachment_id:
            raise SupplierRiskError("Dokument nebyl nalezen.")
        original_attachment_id = document.attachment_id
        company, reused = self._resolve_company(
            company_id=company_id,
            name=name,
            ico=ico,
        )
        document.company_id = company.id
        document.received_on = received_on
        document.note = (note or "").strip()
        if prepared_on is not _KEEP_PREPARED_ON:
            document.prepared_on = prepared_on
        document.attachment_id = original_attachment_id
        document.updated_at = datetime.now()
        self.repository.update_document(document)
        return SupplierRiskSaveResult(
            row=self._require_row(document_id),
            reused_existing_company=reused,
        )

    def open_document(self, document_id: int, parent=None) -> bool:
        row = self._require_row(document_id)
        attachment = attachment_service.repository.get_by_id(row.attachment_id)
        if attachment is None:
            raise SupplierRiskError("Soubor dokumentu nebyl v úložišti nalezen.")
        path = attachment_service.resolve_path(attachment)
        if not path.is_file():
            raise SupplierRiskError("Soubor dokumentu nebyl v úložišti nalezen.")
        return bool(open_local_file(path, parent=parent, title="Dokument rizik"))

    def _resolve_company(
        self,
        *,
        company_id: int | None,
        name: str,
        ico: str | None,
    ) -> tuple[SupplierRiskCompany, bool]:
        cleaned_name = (name or "").strip()
        if not cleaned_name:
            raise SupplierRiskError("Název firmy je povinný.")
        normalized_ico = normalize_supplier_ico(ico)
        existing = (
            self.repository.get_by_ico(normalized_ico) if normalized_ico else None
        )
        if company_id is None:
            if not normalized_ico:
                raise SupplierRiskError("IČO je povinné.")
            if existing is not None:
                return existing, True
            return self._insert_company(cleaned_name, normalized_ico), False

        current = self.repository.get_company(company_id)
        if current is None:
            raise SupplierRiskError("Firma nebyla nalezena.")
        if existing is not None and existing.id != current.id:
            return existing, True
        stored_ico = _stored_ico(current.ico)
        if current.name == cleaned_name and stored_ico == normalized_ico:
            return current, False
        if not normalized_ico:
            raise SupplierRiskError("IČO je povinné.")
        current.name = cleaned_name
        current.ico = normalized_ico
        current.updated_at = datetime.now()
        return self.repository.update_company(current), False

    def _insert_company(self, name: str, ico: str | None) -> SupplierRiskCompany:
        try:
            return self.repository.add_company(
                SupplierRiskCompany(
                    name=name,
                    ico=ico,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
        except IntegrityError:
            if not ico:
                raise
            existing = self.repository.get_by_ico(ico)
            if existing is None:
                raise
            return existing

    def _require_row(self, document_id: int) -> SupplierRiskDocumentRow:
        for document, company, attachment in self.repository.list_rows():
            if document.id == document_id:
                row = self._row(document, company, attachment)
                if not row.attachment_id:
                    raise SupplierRiskError("Dokument nebyl nalezen.")
                return row
        raise SupplierRiskError("Dokument nebyl nalezen.")

    @staticmethod
    def _row(document, company, attachment) -> SupplierRiskDocumentRow:
        return SupplierRiskDocumentRow(
            id=int(document.id),
            company_id=int(company.id),
            company_name=company.name or "",
            ico=company.ico or "",
            filename=(attachment.filename if attachment is not None else "") or "",
            prepared_on=document.prepared_on,
            received_on=document.received_on,
            note=document.note or "",
            attachment_id=int(document.attachment_id or 0),
            stored_path=(attachment.stored_path if attachment is not None else "") or "",
        )


supplier_risk_service = SupplierRiskService()
