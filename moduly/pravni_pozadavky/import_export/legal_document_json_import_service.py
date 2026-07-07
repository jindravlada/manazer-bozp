import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


@dataclass(frozen=True)
class LegalDocumentJsonImportResult:
    document_id: int
    version_id: int
    section_count: int


class LegalDocumentJsonImportService:
    def import_from_file(self, path: str | Path) -> LegalDocumentJsonImportResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise ValueError("Soubor pro import nebyl nalezen.")

        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("Soubor pro import nelze načíst.") from exc

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Soubor neobsahuje platný JSON.") from exc

        return self.import_data(data)

    def import_data(self, data) -> LegalDocumentJsonImportResult:
        if not isinstance(data, dict):
            raise ValueError("Import musí obsahovat JSON objekt.")

        if "document" not in data:
            raise ValueError("Import musí obsahovat sekci document.")
        if "version" not in data:
            raise ValueError("Import musí obsahovat sekci version.")
        if "sections" not in data:
            raise ValueError("Import musí obsahovat sekci sections.")
        if not isinstance(data["sections"], list):
            raise ValueError("Pole sections musí být seznam.")

        document_data = data["document"]
        version_data = data["version"]
        sections_data = data["sections"]

        if not isinstance(document_data, dict):
            raise ValueError("Sekce document musí být objekt.")
        if not isinstance(version_data, dict):
            raise ValueError("Sekce version musí být objekt.")

        document = legal_document_service.create(
            document_type=self._normalize_document_type(document_data.get("document_type")),
            title=self._required_text(document_data.get("title"), "Název předpisu je povinný."),
            number=self._optional_text(document_data.get("number")),
            year=self._optional_int(document_data.get("year")),
            short_title=self._optional_text(document_data.get("short_title")),
            valid_from=self._parse_date(document_data.get("valid_from")),
            valid_to=self._parse_date(document_data.get("valid_to")),
            effective_from=self._parse_date(document_data.get("effective_from")),
            effective_to=self._parse_date(document_data.get("effective_to")),
            source_url=self._optional_text(document_data.get("source_url")),
            local_file_path=self._optional_text(document_data.get("local_file_path")),
            note=self._optional_text(document_data.get("note")),
        )

        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name=self._required_text(
                version_data.get("version_name"),
                "Název verze je povinný.",
            ),
            valid_from=self._parse_date(version_data.get("valid_from")),
            valid_to=self._parse_date(version_data.get("valid_to")),
            effective_from=self._parse_date(version_data.get("effective_from")),
            effective_to=self._parse_date(version_data.get("effective_to")),
            publication_date=self._parse_date(version_data.get("publication_date")),
            source_url=self._optional_text(version_data.get("source_url")),
            local_file_path=self._optional_text(version_data.get("local_file_path")),
            checksum=self._optional_text(version_data.get("checksum")),
            note=self._optional_text(version_data.get("note")),
        )

        section_count = 0
        for index, section_data in enumerate(sections_data):
            if not isinstance(section_data, dict):
                raise ValueError(f"Část předpisu na pozici {index + 1} musí být objekt.")
            legal_section_service.create(
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=self._optional_text(section_data.get("section_type")),
                parent_section_id=self._optional_int(section_data.get("parent_section_id")),
                section_number=self._optional_text(section_data.get("section_number")),
                paragraph=self._optional_text(section_data.get("paragraph")),
                item_letter=self._optional_text(section_data.get("item_letter")),
                title=self._optional_text(section_data.get("title")),
                text=self._optional_text(section_data.get("text")),
                sort_order=self._optional_int(section_data.get("sort_order"), default=0) or 0,
                note=self._optional_text(section_data.get("note")),
            )
            section_count += 1

        return LegalDocumentJsonImportResult(
            document_id=document.id,
            version_id=version.id,
            section_count=section_count,
        )

    def _normalize_document_type(self, value) -> str:
        normalized = (str(value or "")).strip().lower()
        if not normalized:
            raise ValueError("Typ předpisu je povinný.")

        if normalized in VALID_DOCUMENT_TYPES:
            return normalized

        by_label = {label.lower(): key for key, label in DOCUMENT_TYPE_LABELS.items()}
        if normalized in by_label:
            return by_label[normalized]

        raise ValueError(f"Neplatný typ předpisu: {value}")

    def _required_text(self, value, message: str) -> str:
        text = self._optional_text(value)
        if not text:
            raise ValueError(message)
        return text

    def _optional_text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _optional_int(self, value, *, default: int | None = None) -> int | None:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            raise ValueError("Neplatná číselná hodnota.")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Neplatná číselná hodnota.") from exc

    def _parse_date(self, value) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"Neplatné datum: {value}") from exc


legal_document_json_import_service = LegalDocumentJsonImportService()
