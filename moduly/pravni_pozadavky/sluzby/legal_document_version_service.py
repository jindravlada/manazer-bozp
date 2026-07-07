from datetime import date

from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.repository.legal_document_version_repository import (
    LegalDocumentVersionRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class LegalDocumentVersionService:
    def __init__(self):
        self.repository = LegalDocumentVersionRepository()

    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalDocumentVersion]:
        return self.repository.list_by_document(
            document_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, version_id: int) -> LegalDocumentVersion | None:
        return self.repository.get_by_id(version_id)

    def create(
        self,
        *,
        legal_document_id: int,
        version_name: str,
        valid_from: date | None = None,
        valid_to: date | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        publication_date: date | None = None,
        source_url: str = "",
        local_file_path: str = "",
        checksum: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalDocumentVersion:
        self._validate_document_id(legal_document_id)
        normalized_name = version_name.strip()
        if not normalized_name:
            raise ValueError("Název verze je povinný.")

        version = LegalDocumentVersion(
            legal_document_id=legal_document_id,
            version_name=normalized_name,
            valid_from=valid_from,
            valid_to=valid_to,
            effective_from=effective_from,
            effective_to=effective_to,
            publication_date=publication_date,
            source_url=source_url.strip(),
            local_file_path=local_file_path.strip(),
            checksum=checksum.strip(),
            note=note.strip(),
            active=active,
        )
        return self.repository.create(version)

    def update(
        self,
        version_id: int,
        *,
        legal_document_id: int,
        version_name: str,
        valid_from: date | None = None,
        valid_to: date | None = None,
        effective_from: date | None = None,
        effective_to: date | None = None,
        publication_date: date | None = None,
        source_url: str = "",
        local_file_path: str = "",
        checksum: str = "",
        note: str = "",
        active: bool = True,
    ) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None

        self._validate_document_id(legal_document_id)
        normalized_name = version_name.strip()
        if not normalized_name:
            raise ValueError("Název verze je povinný.")

        version.legal_document_id = legal_document_id
        version.version_name = normalized_name
        version.valid_from = valid_from
        version.valid_to = valid_to
        version.effective_from = effective_from
        version.effective_to = effective_to
        version.publication_date = publication_date
        version.source_url = source_url.strip()
        version.local_file_path = local_file_path.strip()
        version.checksum = checksum.strip()
        version.note = note.strip()
        version.active = active
        return self.repository.update(version)

    def deactivate(self, version_id: int) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        version.active = False
        return self.repository.update(version)

    def restore(self, version_id: int) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        version.active = True
        return self.repository.update(version)

    def _validate_document_id(self, legal_document_id: int) -> None:
        if not isinstance(legal_document_id, int) or legal_document_id <= 0:
            raise ValueError("Právní předpis je povinný.")
        if legal_document_service.get_by_id(legal_document_id) is None:
            raise ValueError("Právní předpis nebyl nalezen.")


legal_document_version_service = LegalDocumentVersionService()
