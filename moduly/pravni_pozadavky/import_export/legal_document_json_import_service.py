import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from moduly.pravni_pozadavky.legal_document_type_utils import normalize_document_type
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


def _debug(message: str) -> None:
    print(f"[LegalDocumentJsonImport] {message}", flush=True)


def _debug_section_save(
    *,
    sort_order: int,
    section_type: str,
    section_number: str,
    title: str,
    text: str,
    parent_sort_order: int | None,
) -> None:
    _debug(
        "ukládám sekci: "
        f"sort_order={sort_order}, "
        f"type={section_type}, "
        f"number={section_number}, "
        f"title={title}, "
        f"text_length={len(text)}, "
        f"parent={parent_sort_order if parent_sort_order is not None else '-'}"
    )


def _debug_section_save_error(
    *,
    sort_order: int,
    section_type: str,
    section_number: str,
    title: str,
    text: str,
    parent_sort_order: int | None,
    exc: Exception,
) -> None:
    print("ERROR při ukládání sekce:", flush=True)
    print(
        f"  sort_order={sort_order}\n"
        f"  type={section_type}\n"
        f"  number={section_number}\n"
        f"  title={title}\n"
        f"  text_length={len(text)}\n"
        f"  parent={parent_sort_order if parent_sort_order is not None else '-'}",
        flush=True,
    )
    print(f"  výjimka={exc}", flush=True)


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
            document_type=normalize_document_type(document_data.get("document_type")),
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
            included_in_processes=False,
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
        created_sections: list[tuple] = []
        sort_order_to_id: dict[int, int] = {}

        for index, section_data in enumerate(sections_data):
            if not isinstance(section_data, dict):
                raise ValueError(f"Část předpisu na pozici {index + 1} musí být objekt.")
            sort_order = self._optional_int(section_data.get("sort_order"), default=0) or 0
            section_type = self._optional_text(section_data.get("section_type"))
            section_number = self._optional_text(section_data.get("section_number"))
            title = self._optional_text(section_data.get("title"))
            text = self._optional_text(section_data.get("text"))
            parent_sort_order = self._optional_int(section_data.get("parent_sort_order"))
            _debug_section_save(
                sort_order=sort_order,
                section_type=section_type,
                section_number=section_number,
                title=title,
                text=text,
                parent_sort_order=parent_sort_order,
            )
            try:
                section = legal_section_service.create(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    section_type=section_type,
                    parent_section_id=None,
                    section_number=section_number,
                    paragraph=self._optional_text(section_data.get("paragraph")),
                    item_letter=self._optional_text(section_data.get("item_letter")),
                    title=title,
                    text=text,
                    sort_order=sort_order,
                    note=self._optional_text(section_data.get("note")),
                )
            except Exception as exc:
                _debug_section_save_error(
                    sort_order=sort_order,
                    section_type=section_type,
                    section_number=section_number,
                    title=title,
                    text=text,
                    parent_sort_order=parent_sort_order,
                    exc=exc,
                )
                raise
            created_sections.append((section, section_data))
            sort_order = self._optional_int(section_data.get("sort_order"), default=section.sort_order)
            if sort_order is not None:
                sort_order_to_id[sort_order] = section.id
            section_count += 1

        for section, section_data in created_sections:
            parent_sort_order = self._optional_int(section_data.get("parent_sort_order"))
            if parent_sort_order is None:
                continue
            parent_section_id = sort_order_to_id.get(parent_sort_order)
            if parent_section_id is None:
                continue
            legal_section_service.update(
                section.id,
                legal_document_id=document.id,
                legal_document_version_id=version.id,
                section_type=section.section_type,
                parent_section_id=parent_section_id,
                section_number=section.section_number,
                paragraph=section.paragraph,
                item_letter=section.item_letter,
                title=section.title,
                text=section.text,
                sort_order=section.sort_order,
                note=section.note,
                active=section.active,
            )

        return LegalDocumentJsonImportResult(
            document_id=document.id,
            version_id=version.id,
            section_count=section_count,
        )

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
