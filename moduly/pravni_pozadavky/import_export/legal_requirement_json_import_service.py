import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from moduly.pravni_pozadavky.constants import (
    DEFAULT_PROCESSING_STATUS,
    SECTION_ATTACHMENT,
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

REQUIREMENT_IMPORT_STATUS_CREATED = "Vytvořeno"
REQUIREMENT_IMPORT_STATUS_EXTENDED = "Rozšířeno"
REQUIREMENT_IMPORT_STATUS_ERROR = "Chyba"
REQUIREMENT_IMPORT_STATUS_SKIPPED = "Přeskočeno"

REQUIREMENT_IMPORT_STATUS_OK = REQUIREMENT_IMPORT_STATUS_CREATED

DUPLICATE_SKIP_MESSAGE = "Požadavek již existuje"
ALL_SOURCES_ALREADY_LINKED_MESSAGE = "Všechny podklady již existují"
ARCHIVED_PROCESS_CODE_MESSAGE = "Proces s tímto kódem je archivovaný."

_IMPORTABLE_SECTION_TYPES = frozenset({
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
    SECTION_LETTER,
    SECTION_ATTACHMENT,
})

_ProvisionProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class LegalRequirementJsonImportSource:
    document_number: str
    document_year: int
    provision_label: str


@dataclass(frozen=True)
class LegalRequirementJsonImportItem:
    document_number: str
    document_year: int
    provision_label: str
    sources: tuple[LegalRequirementJsonImportSource, ...]
    process_code: str
    title: str
    fulfillment_text: str
    note: str
    processing_status: str
    update_processing_status: bool


@dataclass(frozen=True)
class LegalRequirementJsonImportRowResult:
    item_label: str
    status: str
    title: str
    error: str


@dataclass(frozen=True)
class LegalRequirementJsonImportSummary:
    total: int
    created_count: int
    extended_count: int
    error_count: int
    skipped_count: int
    rows: list[LegalRequirementJsonImportRowResult]

    @property
    def ok_count(self) -> int:
        return self.created_count


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


def _parse_document_year(raw_item: dict, index: int) -> int:
    year_value = raw_item.get("document_year")
    if year_value is None or str(year_value).strip() == "":
        raise ValueError(f"Položka {index}: document_year je povinné.")
    try:
        return int(year_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Položka {index}: document_year musí být číslo.") from exc


def _parse_import_source(raw_source, index: int, source_index: int) -> LegalRequirementJsonImportSource:
    if not isinstance(raw_source, dict):
        raise ValueError(f"Položka {index}, podklad {source_index}: není objekt.")

    document_number = str(raw_source.get("document_number", "")).strip()
    if not document_number:
        raise ValueError(f"Položka {index}, podklad {source_index}: document_number je povinné.")

    document_year = _parse_document_year(raw_source, index)

    provision_label = str(raw_source.get("provision_label", "")).strip()
    if not provision_label:
        raise ValueError(f"Položka {index}, podklad {source_index}: provision_label je povinné.")

    return LegalRequirementJsonImportSource(
        document_number=document_number,
        document_year=document_year,
        provision_label=provision_label,
    )


def _parse_import_sources(raw_item: dict, index: int) -> tuple[LegalRequirementJsonImportSource, ...]:
    raw_sources = raw_item.get("sources")
    if raw_sources is None:
        return (
            LegalRequirementJsonImportSource(
                document_number=str(raw_item.get("document_number", "")).strip(),
                document_year=_parse_document_year(raw_item, index),
                provision_label=str(raw_item.get("provision_label", "")).strip(),
            ),
        )

    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError(f"Položka {index}: sources musí být neprázdný seznam.")

    return tuple(
        _parse_import_source(raw_source, index, source_index)
        for source_index, raw_source in enumerate(raw_sources, start=1)
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

        document_year = _parse_document_year(raw_item, index)
        provision_label = str(raw_item.get("provision_label", "")).strip()
        if not provision_label:
            raise ValueError(f"Položka {index}: provision_label je povinné.")

        sources = _parse_import_sources(raw_item, index)
        for source_index, source in enumerate(sources, start=1):
            if not source.document_number:
                raise ValueError(f"Položka {index}, podklad {source_index}: document_number je povinné.")
            if not source.provision_label:
                raise ValueError(
                    f"Položka {index}, podklad {source_index}: provision_label je povinné.",
                )

        raw_processing_status = raw_item.get("processing_status")
        if raw_processing_status is None:
            processing_status = DEFAULT_PROCESSING_STATUS
            update_processing_status = False
        else:
            processing_status = str(raw_processing_status).strip()
            update_processing_status = bool(processing_status)
            if not processing_status:
                processing_status = DEFAULT_PROCESSING_STATUS

        items.append(
            LegalRequirementJsonImportItem(
                document_number=document_number,
                document_year=document_year,
                provision_label=provision_label,
                sources=sources,
                process_code=str(raw_item.get("process_code", "")).strip(),
                title=str(raw_item.get("title", "")).strip(),
                fulfillment_text=str(raw_item.get("fulfillment_text", "")).strip(),
                note=str(raw_item.get("note", "")).strip(),
                processing_status=processing_status,
                update_processing_status=update_processing_status,
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
            created_count=sum(
                1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_CREATED
            ),
            extended_count=sum(
                1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_EXTENDED
            ),
            error_count=sum(1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_ERROR),
            skipped_count=sum(
                1 for row in rows if row.status == REQUIREMENT_IMPORT_STATUS_SKIPPED
            ),
            rows=rows,
        )

    def _import_item(self, item: LegalRequirementJsonImportItem) -> LegalRequirementJsonImportRowResult:
        item_label = self._item_label(item)
        resolved_sections = self._resolve_sections(item)

        if item.process_code:
            return self._import_item_with_process_code(item, item_label, resolved_sections)
        return self._import_item_legacy(item, item_label, resolved_sections)

    def _import_item_with_process_code(
        self,
        item: LegalRequirementJsonImportItem,
        item_label: str,
        resolved_sections: list[tuple],
    ) -> LegalRequirementJsonImportRowResult:
        existing = legal_requirement_service.get_by_process_code(item.process_code)
        if existing is not None:
            return self._extend_existing_process(
                existing,
                item,
                item_label,
                resolved_sections,
            )

        archived = legal_requirement_service.get_by_process_code(
            item.process_code,
            active_only=False,
        )
        if archived is not None:
            raise ValueError(ARCHIVED_PROCESS_CODE_MESSAGE)

        return self._create_new_process(
            item,
            item_label,
            resolved_sections,
            process_code=item.process_code,
        )

    def _import_item_legacy(
        self,
        item: LegalRequirementJsonImportItem,
        item_label: str,
        resolved_sections: list[tuple],
    ) -> LegalRequirementJsonImportRowResult:
        for _document, section in resolved_sections:
            existing = legal_requirement_service.get_by_source_section_id(section.id)
            if existing is not None:
                return LegalRequirementJsonImportRowResult(
                    item_label=item_label,
                    status=REQUIREMENT_IMPORT_STATUS_SKIPPED,
                    title=existing.title or existing.regulation_name or item.title,
                    error=DUPLICATE_SKIP_MESSAGE,
                )

        return self._create_new_process(item, item_label, resolved_sections)

    def _extend_existing_process(
        self,
        requirement,
        item: LegalRequirementJsonImportItem,
        item_label: str,
        resolved_sections: list[tuple],
    ) -> LegalRequirementJsonImportRowResult:
        attached_count = 0
        skipped_count = 0

        for _document, section in resolved_sections:
            existing = legal_requirement_service.get_by_source_section_id(section.id)
            if existing is not None:
                if existing.id == requirement.id:
                    skipped_count += 1
                    continue
                raise ValueError("Ustanovení je již přiřazeno jinému procesu.")
            legal_requirement_service.attach_source_section(requirement.id, section.id)
            attached_count += 1

        display_title = requirement.title or requirement.regulation_name or item.title

        if attached_count == 0:
            return LegalRequirementJsonImportRowResult(
                item_label=item_label,
                status=REQUIREMENT_IMPORT_STATUS_SKIPPED,
                title=display_title,
                error=ALL_SOURCES_ALREADY_LINKED_MESSAGE,
            )

        self._apply_optional_updates(requirement.id, item)
        detail_parts = [f"Připojeno podkladů: {attached_count}"]
        if skipped_count:
            detail_parts.append(f"Přeskočeno duplicit: {skipped_count}")

        return LegalRequirementJsonImportRowResult(
            item_label=item_label,
            status=REQUIREMENT_IMPORT_STATUS_EXTENDED,
            title=display_title,
            error="; ".join(detail_parts),
        )

    def _create_new_process(
        self,
        item: LegalRequirementJsonImportItem,
        item_label: str,
        resolved_sections: list[tuple],
        *,
        process_code: str = "",
    ) -> LegalRequirementJsonImportRowResult:
        primary_document, primary_section = resolved_sections[0]
        sections_by_id = legal_section_service.build_sections_map([primary_section])
        source_section_ids = [section.id for _document, section in resolved_sections]
        legal_requirement_service.create_requirement(
            title=item.title,
            process_code=process_code or None,
            regulation_name=(primary_document.title or "").strip(),
            regulation_number=legal_document_regulation_number(primary_document),
            provision=legal_section_provision_label(primary_section, sections_by_id=sections_by_id),
            legal_document_id=primary_document.id,
            legal_section_id=primary_section.id,
            source_section_id=primary_section.id,
            source_section_ids=source_section_ids,
            requirement_summary=item.fulfillment_text,
            note=item.note,
            processing_status=item.processing_status,
        )
        return LegalRequirementJsonImportRowResult(
            item_label=item_label,
            status=REQUIREMENT_IMPORT_STATUS_CREATED,
            title=item.title,
            error="",
        )

    def _resolve_sections(
        self,
        item: LegalRequirementJsonImportItem,
    ) -> list[tuple]:
        resolved_sections = []
        for source in item.sources:
            document = self._find_active_document(source.document_number, source.document_year)
            if document is None:
                raise ValueError("Právní předpis nebyl nalezen.")

            section = self._find_section_by_provision_label(document.id, source.provision_label)
            if section is None:
                raise ValueError("Ustanovení nebylo nalezeno.")
            resolved_sections.append((document, section))
        return resolved_sections

    def _apply_optional_updates(self, requirement_id: int, item: LegalRequirementJsonImportItem) -> None:
        legal_requirement_service.patch_import_metadata(
            requirement_id,
            requirement_summary=item.fulfillment_text or None,
            note=item.note or None,
            processing_status=item.processing_status if item.update_processing_status else None,
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
        process_prefix = f"{item.process_code} – " if item.process_code else ""
        if len(item.sources) == 1:
            source = item.sources[0]
            number = normalize_document_number(source.document_number)
            return f"{process_prefix}{number}/{source.document_year} – {source.provision_label}"
        labels = []
        for source in item.sources:
            number = normalize_document_number(source.document_number)
            labels.append(f"{number}/{source.document_year} – {source.provision_label}")
        title = item.title or "Požadavek"
        return f"{process_prefix}{title} ({len(item.sources)} podkladů: {', '.join(labels)})"

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
