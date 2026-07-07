import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


@dataclass(frozen=True)
class LegalDocumentJsonExportResult:
    document_id: int
    document_title: str
    version_name: str
    section_count: int


class LegalDocumentJsonExportService:
    def export_to_file(self, document_id: int, path: str | Path) -> LegalDocumentJsonExportResult:
        data = self.build_data(document_id)
        file_path = Path(path)

        try:
            file_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise ValueError("Exportovaný soubor nelze zapsat.") from exc

        document = legal_document_service.get_by_id(document_id)
        version_name = data["version"]["version_name"]
        return LegalDocumentJsonExportResult(
            document_id=document_id,
            document_title=document.title if document is not None else "",
            version_name=version_name,
            section_count=len(data["sections"]),
        )

    def build_data(self, document_id: int) -> dict:
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            raise ValueError("Právní předpis nebyl nalezen.")

        active_versions = legal_document_version_service.list_by_document(
            document_id,
            include_inactive=False,
        )
        if not active_versions:
            raise ValueError("Právní předpis nemá žádnou aktivní verzi.")

        version = active_versions[0]
        sections = legal_section_service.list_by_version(
            version.id,
            include_inactive=False,
        )

        return {
            "document": self._serialize_document(document),
            "version": self._serialize_version(version),
            "sections": [self._serialize_section(section) for section in sections],
        }

    def _serialize_document(self, document) -> dict:
        return {
            "document_type": DOCUMENT_TYPE_LABELS.get(
                document.document_type,
                document.document_type,
            ),
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
        }

    def _serialize_version(self, version) -> dict:
        return {
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
        }

    def _serialize_section(self, section) -> dict:
        return {
            "section_type": self._text(section.section_type),
            "section_number": self._text(section.section_number),
            "paragraph": self._text(section.paragraph),
            "item_letter": self._text(section.item_letter),
            "title": self._text(section.title),
            "text": self._text(section.text),
            "sort_order": section.sort_order,
            "note": self._text(section.note),
        }

    def _text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _serialize_date(self, value: date | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


legal_document_json_export_service = LegalDocumentJsonExportService()
