import json
import re
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

        def flush_current() -> None:
            nonlocal current, awaiting_paragraph_title, sort_order
            if current is not None and self._has_content(current):
                sort_order += 1
                current.sort_order = sort_order
                sections.append(current)
                self._debug_section(current)
            current = None
            awaiting_paragraph_title = False

        def start_section(**kwargs) -> None:
            nonlocal current, awaiting_paragraph_title
            flush_current()
            current = ParsedLegalSection(**kwargs)
            awaiting_paragraph_title = kwargs.get("section_type") == SECTION_PARAGRAPH

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

        flush_current()
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
        if identifier:
            _debug(f"{label} {identifier} text={len(section.text)}")
        else:
            _debug(f"{label} text={len(section.text)}")

    def _has_content(self, section: ParsedLegalSection) -> bool:
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
