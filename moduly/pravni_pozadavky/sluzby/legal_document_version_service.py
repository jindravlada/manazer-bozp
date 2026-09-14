from datetime import date

from sqlalchemy.exc import IntegrityError

from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.repository.legal_document_version_repository import (
    LegalDocumentVersionRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_temporal import (
    SOURCE_ELI_UNSET,
    normalize_stored_source_eli,
    select_effective_version,
)

DUPLICATE_SOURCE_ELI_MESSAGE = "Časové znění s tímto ELI už u předpisu existuje."


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

    def get_effective_version(
        self,
        document_id: int,
        on_date: date,
        *,
        include_pending: bool = False,
    ) -> LegalDocumentVersion | None:
        versions = self.list_by_document(document_id, include_inactive=False)
        return select_effective_version(
            versions,
            on_date,
            include_pending=include_pending,
        )

    def get_current_version(self, document_id: int) -> LegalDocumentVersion | None:
        return self.get_effective_version(document_id, date.today())

    def find_pending_by_checksum(
        self,
        document_id: int,
        checksum: str,
    ) -> LegalDocumentVersion | None:
        return self.repository.find_pending_by_checksum(document_id, checksum)

    def find_by_checksum(
        self,
        document_id: int,
        checksum: str,
    ) -> LegalDocumentVersion | None:
        return self.repository.find_by_checksum(document_id, checksum)

    def find_by_source_eli(
        self,
        document_id: int,
        source_eli: str | None,
    ) -> LegalDocumentVersion | None:
        return self.repository.find_by_source_eli(document_id, source_eli)

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
        source_eli: str | None = None,
        source_url: str = "",
        local_file_path: str = "",
        checksum: str = "",
        note: str = "",
        pending_adoption: bool = False,
        future_wording: bool = False,
        active: bool = True,
    ) -> LegalDocumentVersion:
        self._validate_document_id(legal_document_id)
        normalized_name = version_name.strip()
        if not normalized_name:
            raise ValueError("Název verze je povinný.")
        normalized_source_eli = normalize_stored_source_eli(source_eli)
        self._ensure_unique_source_eli(legal_document_id, normalized_source_eli)

        version = LegalDocumentVersion(
            legal_document_id=legal_document_id,
            version_name=normalized_name,
            valid_from=valid_from,
            valid_to=valid_to,
            effective_from=effective_from,
            effective_to=effective_to,
            publication_date=publication_date,
            source_eli=normalized_source_eli,
            source_url=source_url.strip(),
            local_file_path=local_file_path.strip(),
            checksum=checksum.strip(),
            note=note.strip(),
            pending_adoption=pending_adoption,
            future_wording=future_wording,
            active=active,
        )
        return self._persist_create(version)

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
        source_eli=SOURCE_ELI_UNSET,
        source_url: str = "",
        local_file_path: str = "",
        checksum: str = "",
        note: str = "",
        pending_adoption: bool | None = None,
        future_wording: bool | None = None,
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
        if source_eli is not SOURCE_ELI_UNSET:
            normalized_source_eli = normalize_stored_source_eli(source_eli)
            self._ensure_unique_source_eli(
                legal_document_id,
                normalized_source_eli,
                exclude_version_id=version.id,
            )
            version.source_eli = normalized_source_eli
        version.source_url = source_url.strip()
        version.local_file_path = local_file_path.strip()
        version.checksum = checksum.strip()
        version.note = note.strip()
        if pending_adoption is not None:
            version.pending_adoption = pending_adoption
        if future_wording is not None:
            version.future_wording = future_wording
        version.active = active
        return self._persist_update(version)

    def update_checksum(self, version_id: int, checksum: str) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        version.checksum = checksum.strip()
        return self.repository.update(version)

    def apply_official_wording_identifiers(
        self,
        version_id: int,
        *,
        source_eli: str,
        checksum: str,
        effective_from: date | None = None,
        source_url: str = "",
    ) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        normalized_eli = normalize_stored_source_eli(source_eli)
        if normalized_eli:
            existing = self.repository.find_by_source_eli(
                version.legal_document_id,
                normalized_eli,
            )
            if existing is None or existing.id == version.id:
                version.source_eli = normalized_eli
                if effective_from is not None:
                    version.effective_from = effective_from
        version.checksum = checksum.strip()
        if source_url.strip():
            version.source_url = source_url.strip()
        return self._persist_update(version)

    def set_pending_adoption(
        self,
        version_id: int,
        pending_adoption: bool,
    ) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        version.pending_adoption = pending_adoption
        if not pending_adoption:
            version.future_wording = False
        return self.repository.update(version)

    def retire_source_eli(self, version_id: int) -> LegalDocumentVersion | None:
        version = self.repository.get_by_id(version_id)
        if version is None:
            return None
        version.source_eli = None
        version.active = False
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

    def _ensure_unique_source_eli(
        self,
        legal_document_id: int,
        source_eli: str | None,
        *,
        exclude_version_id: int | None = None,
    ) -> None:
        if not source_eli:
            return
        existing = self.repository.find_by_source_eli(legal_document_id, source_eli)
        if existing is None:
            return
        if exclude_version_id is not None and existing.id == exclude_version_id:
            return
        raise ValueError(DUPLICATE_SOURCE_ELI_MESSAGE)

    def _persist_create(self, version: LegalDocumentVersion) -> LegalDocumentVersion:
        try:
            return self.repository.create(version)
        except IntegrityError as exc:
            raise ValueError(DUPLICATE_SOURCE_ELI_MESSAGE) from exc

    def _persist_update(self, version: LegalDocumentVersion) -> LegalDocumentVersion:
        try:
            return self.repository.update(version)
        except IntegrityError as exc:
            raise ValueError(DUPLICATE_SOURCE_ELI_MESSAGE) from exc

    def _validate_document_id(self, legal_document_id: int) -> None:
        if not isinstance(legal_document_id, int) or legal_document_id <= 0:
            raise ValueError("Právní předpis je povinný.")
        if legal_document_service.get_by_id(legal_document_id) is None:
            raise ValueError("Právní předpis nebyl nalezen.")


legal_document_version_service = LegalDocumentVersionService()
