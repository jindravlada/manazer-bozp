from datetime import date

from moduly.pravni_pozadavky.constants import VALID_DOCUMENT_TYPES
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.repository.legal_document_repository import LegalDocumentRepository


class LegalDocumentService:
    def __init__(self):
        self.repository = LegalDocumentRepository()

    def list_all(self, *, include_inactive: bool = False) -> list[LegalDocument]:
        return self.repository.list_all(include_inactive=include_inactive)

    def get_by_id(self, document_id: int) -> LegalDocument | None:
        return self.repository.get_by_id(document_id)

    def create(
        self,
        *,
        document_type: str,
        title: str,
        number: str = "",
        year: int | None = None,
        short_title: str = "",
        valid_from: date | None = None,
        valid_to: date | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        source_url: str = "",
        local_file_path: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalDocument:
        normalized_type = self._normalize_document_type(document_type)
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název právního předpisu je povinný.")

        document = LegalDocument(
            document_type=normalized_type,
            number=number.strip(),
            year=year,
            title=normalized_title,
            short_title=short_title.strip(),
            valid_from=valid_from,
            valid_to=valid_to,
            effective_from=effective_from,
            effective_to=effective_to,
            source_url=source_url.strip(),
            local_file_path=local_file_path.strip(),
            note=note.strip(),
            active=active,
        )
        return self.repository.create(document)

    def update(
        self,
        document_id: int,
        *,
        document_type: str,
        title: str,
        number: str = "",
        year: int | None = None,
        short_title: str = "",
        valid_from: date | None = None,
        valid_to: date | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        source_url: str = "",
        local_file_path: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalDocument | None:
        document = self.repository.get_by_id(document_id)
        if document is None:
            return None

        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Název právního předpisu je povinný.")

        document.document_type = self._normalize_document_type(document_type)
        document.number = number.strip()
        document.year = year
        document.title = normalized_title
        document.short_title = short_title.strip()
        document.valid_from = valid_from
        document.valid_to = valid_to
        document.effective_from = effective_from
        document.effective_to = effective_to
        document.source_url = source_url.strip()
        document.local_file_path = local_file_path.strip()
        document.note = note.strip()
        document.active = active
        return self.repository.update(document)

    def deactivate(self, document_id: int) -> LegalDocument | None:
        document = self.repository.get_by_id(document_id)
        if document is None:
            return None
        document.active = False
        return self.repository.update(document)

    def restore(self, document_id: int) -> LegalDocument | None:
        document = self.repository.get_by_id(document_id)
        if document is None:
            return None
        document.active = True
        return self.repository.update(document)

    def _normalize_document_type(self, value: str) -> str:
        normalized = (value or "").strip()
        if normalized not in VALID_DOCUMENT_TYPES:
            raise ValueError("Typ právního předpisu je povinný.")
        return normalized


legal_document_service = LegalDocumentService()
