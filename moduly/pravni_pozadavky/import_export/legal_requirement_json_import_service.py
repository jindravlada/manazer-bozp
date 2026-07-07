import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from moduly.pravni_pozadavky.constants import (
    DEFAULT_PROCESSING_STATUS,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

REQUIREMENT_IMPORT_STATUS_OK = "OK"
REQUIREMENT_IMPORT_STATUS_ERROR = "Chyba"
REQUIREMENT_IMPORT_STATUS_SKIPPED = "Přeskočeno"

DUPLICATE_SKIP_MESSAGE = "Požadavek již existuje"

_IMPORTABLE_SECTION_TYPES = frozenset({
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
    SECTION_LETTER,
})

_ProvisionProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class LegalRequirementJsonImportItem:
    document_number: str
    document_year: int
    provision_label: str
    title: str
    fulfillment_text: str
    note: str
    processing_status: str


@dataclass(frozen=True)
class LegalRequirementJsonImportRowResult:
    item_label: str
    status: str
    title: str
    error: str


@dataclass(frozen=True)
class LegalRequirementJsonImportSummary:
    total: int
    ok_count: int
    error_count: int
    skipped_count: int
    rows: list[LegalRequirementJsonImportRowResult]


def normalize_document_number(value: str) -> str:
    text = (value or "").strip()
    match = re.match(r"^(\d+)", text)
    return match.group(1) if match else text


def normalize_provision_label(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    letter_match = re.search(
        r"písm\.\s*([a-záčďéěíňóřšťúůýž])\)",
        text,
        re.IGNORECASE,
    )
    if letter_match is None:
        return text
    letter = letter_match.group(1).lower()
    return (
        text[: letter_match.start()]
        + f"písm. {letter})"
        + text[letter_match.end() :]
    )


def parse_import_items(data) -> list[LegalRequirementJsonImportItem]:
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict) and isinstance(data.get("items"), list):
        raw_items = data["items"]
    else:
        raise ValueError("JSON musí obsahovat seznam položek.")

    items: list[LegalRequirementJsonImportItem] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise ValueError(f"Položka {index} není objekt.")

        document_number = str(raw_item.get("document_number", "")).strip()
        if not document_number:
            raise ValueError(f"Položka {index}: document_number je povinné.")

        year_value = raw_item.get("document_year")
        if year_value is None or str(year_value).strip() == "":
            raise ValueError(f"Položka {index}: document_year je povinné.")
        try:
            document_year = int(year_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Položka {index}: document_year musí být číslo.") from exc

        provision_label = str(raw_item.get("provision_label", "")).strip()
        if not provision_label:
            raise ValueError(f"Položka {index}: provision_label je povinné.")

        processing_status = str(raw_item.get("processing_status", "")).strip()
        items.append(
            LegalRequirementJsonImportItem(
                document_number=document_number,
                document_year=document_year,
                provision_label=provision_label,
                title=str(raw_item.get("title", "")).strip(),
                fulfillment_text=str(raw_item.get("fulfillment_text", "")).strip(),
                note=str(raw_item.get("note", "")).strip(),
                processing_status=processing_status or DEFAULT_PROCESSING_STATUS,
            ),
        )
    return items


class LegalRequirementJsonImportService:
    def import_from_file(
        self,
        path: str | Path,
        *,
        on_progress: _ProvisionProgressCallback | None = None,
    ) -> LegalRequirementJsonImportSummary:
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
            raise ValueError("Soubor není platný JSON.") from exc

        items = parse_import_items(data)
        return self.import_items(items, on_progress=on_progress)

    def import_items(
        self,
        items: list[LegalRequirementJsonImportItem],
        *,
        on_progress: _ProvisionProgressCallback | None = None,
    ) -> LegalRequirementJsonImportSummary:
        rows: list[LegalRequirementJsonImportRowResult] = []
        total = len(items)

        for index, item in enumerate(items, start=1):
            item_label = self._item_label(item)
            self._notify_progress(on_progress, index, total, item_label)

            try:
                row = self._import_item(item)
            except ValueError as exc:
                row = LegalRequirementJsonImportRowResult(
                    item_label=item_label,
                    status=REQUIREMENT_IMPORT_STATUS_ERROR,
                    title=item.title,
                    error=str(exc),
                )
            rows.append(row)

        return LegalRequirementJsonImportSummary(
            total=total,
            ok_count=sum(1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_OK),
            error_count=sum(1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_ERROR),
            skipped_count=sum(
                1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_SKIPPED
            ),
            rows=rows,
        )

    def _import_item(self, item: LegalRequirementJsonImportItem) -> LegalRequirementJsonImportRowResult:
        item_label = self._item_label(item)
        document = self._find_active_document(item.document_number, item.document_year)
        if document is None:
            raise ValueError("Právní předpis nebyl nalezen.")

        section = self._find_section_by_provision_label(document.id, item.provision_label)
        if section is None:
            raise ValueError("Ustanovení nebylo nalezeno.")

        existing = legal_requirement_service.get_by_source_section_id(section.id)
        if existing is not None:
            return LegalRequirementJsonImportRowResult(
                item_label=item_label,
                status=REQUIREMENT_IMPORT_STATUS_SKIPPED,
                title=existing.regulation_name or item.title,
                error=DUPLICATE_SKIP_MESSAGE,
            )

        sections_by_id = legal_section_service.build_sections_map([section])
        legal_requirement_service.create_requirement(
            regulation_name=item.title,
            regulation_number=legal_document_regulation_number(document),
            provision=legal_section_provision_label(section, sections_by_id=sections_by_id),
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            requirement_summary=item.fulfillment_text,
            note=item.note,
            processing_status=item.processing_status,
        )
        return LegalRequirementJsonImportRowResult(
            item_label=item_label,
            status=REQUIREMENT_IMPORT_STATUS_OK,
            title=item.title,
            error="",
        )

    def _find_active_document(self, document_number: str, document_year: int):
        normalized_number = normalize_document_number(document_number)
        for document in legal_document_service.list_all(include_inactive=True):
            if not document.active:
                continue
            stored_number = normalize_document_number(document.number)
            if stored_number == normalized_number and document.year == document_year:
                return document
        return None

    def _find_section_by_provision_label(self, document_id: int, provision_label: str):
        normalized_label = normalize_provision_label(provision_label)
        version = self._select_document_version(document_id)
        if version is None:
            return None

        sections = legal_section_service.list_by_version(version.id)
        sections_by_id = legal_section_service.build_sections_map(sections)
        matches = []
        for section in sections:
            if section.section_type not in _IMPORTABLE_SECTION_TYPES:
                continue
            label = normalize_provision_label(
                legal_section_provision_label(section, sections_by_id=sections_by_id),
            )
            if label == normalized_label:
                matches.append(section)

        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError("Nalezeno více ustanovení se stejným označením.")
        return matches[0]

    def _select_document_version(self, document_id: int):
        versions = [
            version
            for version in legal_document_version_service.list_by_document(document_id)
            if version.active
        ]
        if not versions:
            return None
        return max(versions, key=lambda version: version.id)

    def _item_label(self, item: LegalRequirementJsonImportItem) -> str:
        number = normalize_document_number(item.document_number)
        return f"{number}/{item.document_year} – {item.provision_label}"

    def _notify_progress(
        self,
        on_progress: _ProvisionProgressCallback | None,
        current: int,
        total: int,
        label: str,
    ) -> None:
        if on_progress is not None:
            on_progress(current, total, label)


legal_requirement_json_import_service = LegalRequirementJsonImportService()
