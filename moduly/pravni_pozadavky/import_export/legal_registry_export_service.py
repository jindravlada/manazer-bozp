import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from moduly.pravni_pozadavky.constants import process_code_sort_key
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
from moduly.pravni_pozadavky.modely.legal_section import LegalSection
from moduly.pravni_pozadavky.repository.legal_document_repository import LegalDocumentRepository
from moduly.pravni_pozadavky.repository.legal_document_version_repository import (
    LegalDocumentVersionRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_repository import (
    LegalRequirementRepository,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.repository.legal_section_repository import LegalSectionRepository

EXPORT_VERSION = 1
APPLICATION_NAME = "Manažer BOZP 3.0"


@dataclass(frozen=True)
class LegalRegistryExportResult:
    file_path: Path
    requirement_count: int
    source_count: int
    document_count: int
    version_count: int
    section_count: int


class LegalRegistryExportService:
    def __init__(self):
        self.requirement_repository = LegalRequirementRepository()
        self.source_repository = LegalRequirementSourceRepository()
        self.document_repository = LegalDocumentRepository()
        self.version_repository = LegalDocumentVersionRepository()
        self.section_repository = LegalSectionRepository()

    def build_default_filename(self, *, created_at: datetime | None = None) -> str:
        timestamp = (created_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
        return f"legal_registry_export_{timestamp}.json"

    def build_data(self, *, created_at: datetime | None = None) -> dict:
        created_at = created_at or datetime.now()
        requirements = self.requirement_repository.get_all(active_only=True)
        requirements = sorted(requirements, key=process_code_sort_key)
        sources = self.source_repository.list_for_active_requirements()
        documents = self.document_repository.list_all(include_inactive=False)
        versions = self.version_repository.list_all(include_inactive=False)
        sections = self.section_repository.list_active()

        return {
            "export_version": EXPORT_VERSION,
            "created_at": self._serialize_datetime(created_at),
            "application": APPLICATION_NAME,
            "requirements": [self._serialize_requirement(item) for item in requirements],
            "sources": [self._serialize_source(item) for item in sources],
            "documents": [self._serialize_document(item) for item in documents],
            "versions": [self._serialize_version(item) for item in versions],
            "sections": [self._serialize_section(item) for item in sections],
        }

    def export_to_file(self, path: str | Path) -> LegalRegistryExportResult:
        created_at = datetime.now()
        data = self.build_data(created_at=created_at)
        file_path = Path(path)

        try:
            file_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ValueError("Exportovaný soubor nelze zapsat.") from exc

        return LegalRegistryExportResult(
            file_path=file_path,
            requirement_count=len(data["requirements"]),
            source_count=len(data["sources"]),
            document_count=len(data["documents"]),
            version_count=len(data["versions"]),
            section_count=len(data["sections"]),
        )

    def _serialize_requirement(self, requirement: LegalRequirement) -> dict:
        return {
            "id": requirement.id,
            "title": self._text(requirement.title),
            "process_code": self._text(requirement.process_code),
            "regulation_name": self._text(requirement.regulation_name),
            "regulation_number": self._text(requirement.regulation_number),
            "provision": self._text(requirement.provision),
            "area": self._text(requirement.area),
            "legal_document_id": requirement.legal_document_id,
            "legal_section_id": requirement.legal_section_id,
            "source_section_id": requirement.source_section_id,
            "requirement_summary": self._text(requirement.requirement_summary),
            "organization_impact": self._text(requirement.organization_impact),
            "responsible_person_id": requirement.responsible_person_id,
            "responsible_person_name": self._text(requirement.responsible_person_name),
            "responsible_role_id": requirement.responsible_role_id,
            "responsible_role_name": self._text(requirement.responsible_role_name),
            "verification_periodicity": self._text(requirement.verification_periodicity),
            "last_verification_date": self._serialize_date(requirement.last_verification_date),
            "next_verification_date": self._serialize_date(requirement.next_verification_date),
            "compliance_status": self._text(requirement.compliance_status),
            "processing_status": self._text(requirement.processing_status),
            "note": self._text(requirement.note),
            "active": requirement.active,
            "merged_into_requirement_id": requirement.merged_into_requirement_id,
            "parent_requirement_id": requirement.parent_requirement_id,
            "created_at": self._serialize_datetime(requirement.created_at),
            "updated_at": self._serialize_datetime(requirement.updated_at),
        }

    def _serialize_source(self, source: LegalRequirementSource) -> dict:
        return {
            "id": source.id,
            "requirement_id": source.requirement_id,
            "legal_section_id": source.legal_section_id,
            "sort_order": source.sort_order,
            "created_at": self._serialize_datetime(source.created_at),
        }

    def _serialize_document(self, document: LegalDocument) -> dict:
        return {
            "id": document.id,
            "document_type": self._text(document.document_type),
            "number": self._text(document.number),
            "year": document.year,
            "title": self._text(document.title),
            "short_title": self._text(document.short_title),
            "valid_from": self._serialize_date(document.valid_from),
            "valid_to": self._serialize_date(document.valid_to),
            "effective_from": self._serialize_date(document.effective_from),
            "effective_to": self._serialize_date(document.effective_to),
            "source_url": self._text(document.source_url),
            "local_file_path": self._text(document.local_file_path),
            "note": self._text(document.note),
            "active": document.active,
            "included_in_processes": document.included_in_processes,
            "created_at": self._serialize_datetime(document.created_at),
            "updated_at": self._serialize_datetime(document.updated_at),
        }

    def _serialize_version(self, version: LegalDocumentVersion) -> dict:
        return {
            "id": version.id,
            "legal_document_id": version.legal_document_id,
            "version_name": self._text(version.version_name),
            "valid_from": self._serialize_date(version.valid_from),
            "valid_to": self._serialize_date(version.valid_to),
            "effective_from": self._serialize_date(version.effective_from),
            "effective_to": self._serialize_date(version.effective_to),
            "publication_date": self._serialize_date(version.publication_date),
            "source_url": self._text(version.source_url),
            "local_file_path": self._text(version.local_file_path),
            "checksum": self._text(version.checksum),
            "note": self._text(version.note),
            "active": version.active,
            "created_at": self._serialize_datetime(version.created_at),
            "updated_at": self._serialize_datetime(version.updated_at),
        }

    def _serialize_section(self, section: LegalSection) -> dict:
        return {
            "id": section.id,
            "legal_document_id": section.legal_document_id,
            "legal_document_version_id": section.legal_document_version_id,
            "parent_section_id": section.parent_section_id,
            "section_type": self._text(section.section_type),
            "section_number": self._text(section.section_number),
            "paragraph": self._text(section.paragraph),
            "item_letter": self._text(section.item_letter),
            "title": self._text(section.title),
            "text": self._text(section.text),
            "sort_order": section.sort_order,
            "note": self._text(section.note),
            "active": section.active,
            "created_at": self._serialize_datetime(section.created_at),
            "updated_at": self._serialize_datetime(section.updated_at),
        }

    def _text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _serialize_date(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    def _serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


legal_registry_export_service = LegalRegistryExportService()
