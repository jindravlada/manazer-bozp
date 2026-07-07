import json
import re
from dataclasses import dataclass
from pathlib import Path

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS, VALID_DOCUMENT_TYPES
from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
    LegalDocumentParseResult,
    ParsedLegalSection,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_PART,
    SECTION_SUBSECTION,
)

_PART_RE = re.compile(r"^\s*ČÁST\s+(.+?)\s*$", re.IGNORECASE)
_HEAD_RE = re.compile(r"^\s*HLAVA\s+(.+?)\s*$", re.IGNORECASE)
_DIVISION_RE = re.compile(r"^\s*DÍL\s+(.+?)\s*$", re.IGNORECASE)
_PARAGRAPH_RE = re.compile(r"^\s*§\s*(\d+[a-z]?)\s*(.*)$", re.IGNORECASE)
_SUBSECTION_RE = re.compile(r"^\s*\((\d+)\)\s*(.*)$")
_LETTER_RE = re.compile(r"^\s*([a-záčďéěíňóřšťúůýž])\)\s*(.*)$", re.IGNORECASE)

_SECTION_DEBUG_LABELS = {
    SECTION_PART: "CAST",
    SECTION_HEAD: "HLAVA",
    SECTION_DIVISION: "DIL",
    SECTION_PARAGRAPH: "PARAGRAF",
    SECTION_SUBSECTION: "ODSTAVEC",
    SECTION_LETTER: "PISMENO",
}


def _debug(message: str) -> None:
    print(f"[LegalDocumentParser] {message}", flush=True)


@dataclass
class _HierarchyContext:
    current_part: int | None = None
    current_head: int | None = None
    current_section: int | None = None
    current_paragraph: int | None = None
    current_subsection: int | None = None

    def parent_for(self, section_type: str) -> int | None:
        if section_type == SECTION_PART:
            return None
        if section_type == SECTION_HEAD:
            return self.current_part
        if section_type == SECTION_DIVISION:
            return self.current_head or self.current_part
        if section_type == SECTION_PARAGRAPH:
            return self.current_section or self.current_head or self.current_part
        if section_type == SECTION_SUBSECTION:
            return self.current_paragraph
        if section_type == SECTION_LETTER:
            if self.current_subsection is not None:
                return self.current_subsection
            return self.current_paragraph
        return None

    def register(self, section: ParsedLegalSection) -> None:
        sort_order = section.sort_order
        if section.section_type == SECTION_PART:
            self.current_part = sort_order
            self.current_head = None
            self.current_section = None
            self.current_paragraph = None
            self.current_subsection = None
            return

        if section.section_type == SECTION_HEAD:
            self.current_head = sort_order
            self.current_section = None
            self.current_paragraph = None
            self.current_subsection = None
            return

        if section.section_type == SECTION_DIVISION:
            self.current_section = sort_order
            self.current_paragraph = None
            self.current_subsection = None
            return

        if section.section_type == SECTION_PARAGRAPH:
            self.current_paragraph = sort_order
            self.current_subsection = None
            return

        if section.section_type == SECTION_SUBSECTION:
            self.current_subsection = sort_order
            return


class LegalDocumentParser:
    DEFAULT_VERSION_NAME = "Aktuální znění"

    def __init__(self):
        self._last_result: LegalDocumentParseResult | None = None

    def parse_text(
        self,
        text: str,
        *,
        document_type: str,
        number: str,
        year: int | None,
        title: str,
        short_title: str = "",
    ) -> LegalDocumentParseResult:
        normalized_type = self._normalize_document_type(document_type)
        sections = self._parse_sections(text)
        result = LegalDocumentParseResult(
            document={
                "document_type": DOCUMENT_TYPE_LABELS.get(normalized_type, normalized_type),
                "number": (number or "").strip(),
                "year": year,
                "title": (title or "").strip(),
                "short_title": (short_title or "").strip(),
                "valid_from": None,
                "valid_to": None,
                "effective_from": None,
                "effective_to": None,
                "source_url": "",
                "local_file_path": "",
                "note": "",
            },
            version={
                "version_name": self.DEFAULT_VERSION_NAME,
                "valid_from": None,
                "valid_to": None,
                "effective_from": None,
                "effective_to": None,
                "publication_date": None,
                "source_url": "",
                "local_file_path": "",
                "checksum": "",
                "note": "",
            },
            sections=sections,
        )
        self._last_result = result
        return result

    def export_json(self, path: str | Path, data: LegalDocumentParseResult | dict | None = None) -> None:
        payload = data
        if payload is None:
            if self._last_result is None:
                raise ValueError("Parser nemá žádný výstup k exportu.")
            payload = self._last_result

        if isinstance(payload, LegalDocumentParseResult):
            export_data = payload.to_dict()
        else:
            export_data = payload

        file_path = Path(path)
        file_path.write_text(
            json.dumps(export_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _parse_sections(self, text: str) -> list[ParsedLegalSection]:
        sections: list[ParsedLegalSection] = []
        sort_order = 0
        current: ParsedLegalSection | None = None
        awaiting_paragraph_title = False
        hierarchy = _HierarchyContext()

        def flush_current(*, allow_bare_paragraph: bool = True) -> None:
            nonlocal current, awaiting_paragraph_title, sort_order
            if current is not None and self._has_content(
                current,
                allow_bare_paragraph=allow_bare_paragraph,
            ):
                sort_order += 1
                current.sort_order = sort_order
                current.parent_sort_order = hierarchy.parent_for(current.section_type)
                sections.append(current)
                hierarchy.register(current)
                self._debug_section(current)
            current = None
            awaiting_paragraph_title = False

        def start_section(**kwargs) -> None:
            nonlocal current, awaiting_paragraph_title
            section_type = kwargs.get("section_type")
            flush_current()
            if section_type == SECTION_PARAGRAPH:
                hierarchy.current_subsection = None
            elif section_type == SECTION_SUBSECTION:
                hierarchy.current_subsection = None
            current = ParsedLegalSection(**kwargs)
            awaiting_paragraph_title = section_type == SECTION_PARAGRAPH

        def append_text(line: str) -> None:
            nonlocal current
            if current is None:
                return
            if current.text:
                current.text = f"{current.text}\n{line}"
            else:
                current.text = line

        def process_line(line: str) -> None:
            nonlocal current, awaiting_paragraph_title

            match = _PART_RE.match(line)
            if match:
                start_section(
                    section_type=SECTION_PART,
                    section_number=match.group(1).strip(),
                )
                return

            match = _HEAD_RE.match(line)
            if match:
                start_section(
                    section_type=SECTION_HEAD,
                    section_number=match.group(1).strip(),
                )
                return

            match = _DIVISION_RE.match(line)
            if match:
                start_section(
                    section_type=SECTION_DIVISION,
                    section_number=match.group(1).strip(),
                )
                return

            match = _PARAGRAPH_RE.match(line)
            if match:
                paragraph_number = match.group(1).strip()
                inline_title = match.group(2).strip()
                start_section(
                    section_type=SECTION_PARAGRAPH,
                    paragraph=paragraph_number,
                    title=inline_title,
                )
                awaiting_paragraph_title = not inline_title
                return

            match = _SUBSECTION_RE.match(line)
            if match:
                start_section(
                    section_type=SECTION_SUBSECTION,
                    section_number=match.group(1).strip(),
                    text=match.group(2).strip(),
                )
                return

            match = _LETTER_RE.match(line)
            if match:
                start_section(
                    section_type=SECTION_LETTER,
                    item_letter=match.group(1).lower(),
                    text=match.group(2).strip(),
                )
                return

            if (
                current is not None
                and awaiting_paragraph_title
                and current.section_type == SECTION_PARAGRAPH
                and not current.title
            ):
                current.title = line
                awaiting_paragraph_title = False
                return

            append_text(line)

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            try:
                process_line(line)
            except Exception:
                continue

        flush_current(allow_bare_paragraph=False)
        return sections

    def _debug_section(self, section: ParsedLegalSection) -> None:
        label = _SECTION_DEBUG_LABELS.get(section.section_type, section.section_type.upper())
        if section.section_type == SECTION_PARAGRAPH:
            identifier = f"§{section.paragraph}" if section.paragraph else ""
        elif section.section_type == SECTION_LETTER:
            identifier = section.item_letter
        else:
            identifier = section.section_number
        identifier = identifier.strip()
        parent = section.parent_sort_order
        if identifier:
            _debug(f"{label} {identifier} parent={parent} text={len(section.text)}")
        else:
            _debug(f"{label} parent={parent} text={len(section.text)}")

    def _has_content(self, section: ParsedLegalSection, *, allow_bare_paragraph: bool = True) -> bool:
        if section.section_type == SECTION_PARAGRAPH:
            if section.title.strip() or section.text.strip():
                return True
            if allow_bare_paragraph and section.paragraph.strip():
                return True
            return False
        if section.section_type == SECTION_SUBSECTION:
            return bool(section.section_number.strip() or section.text.strip())
        if section.section_type == SECTION_LETTER:
            return bool(section.item_letter.strip() or section.text.strip())
        return bool(
            section.section_number.strip()
            or section.title.strip()
            or section.text.strip()
        )

    def _normalize_document_type(self, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized in VALID_DOCUMENT_TYPES:
            return normalized

        by_label = {label.lower(): key for key, label in DOCUMENT_TYPE_LABELS.items()}
        if normalized in by_label:
            return by_label[normalized]

        return normalized or "zakon"


legal_document_parser = LegalDocumentParser()
