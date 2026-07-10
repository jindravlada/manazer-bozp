from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from moduly.pravni_pozadavky.constants import (
    SECTION_ATTACHMENT,
    SECTION_DIVISION,
    SECTION_HEAD,
    SECTION_PARAGRAPH,
    SECTION_PART,
)
from moduly.pravni_pozadavky.modely.legal_section import LegalSection
from moduly.pravni_pozadavky.sluzby.legal_section_display_text_service import (
    legal_section_display_text_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_section_tree import build_section_children_map

_PARAGRAPH_QUERY_RE = re.compile(r"^\s*§?\s*(\d+[a-z]?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidTextDocument:
    plain_text: str = ""
    html: str = ""
    paragraph_anchors: dict[str, str] = field(default_factory=dict)


class LegalDocumentValidTextService:
    """Sestaví čitelné platné znění verze předpisu z databázových ustanovení."""

    def compose_version(self, version_id: int) -> ValidTextDocument:
        sections = legal_section_service.list_by_version(version_id, include_inactive=False)
        if not sections:
            return ValidTextDocument()

        children_by_parent = build_section_children_map(sections)
        plain_parts: list[str] = []
        html_parts: list[str] = []
        paragraph_anchors: dict[str, str] = {}

        for section in children_by_parent.get(None, []):
            self._append_section(
                section,
                children_by_parent=children_by_parent,
                plain_parts=plain_parts,
                html_parts=html_parts,
                paragraph_anchors=paragraph_anchors,
            )

        plain_text = self._join_blocks(plain_parts)
        document_html = (
            "<html><head><meta charset='utf-8'></head><body>"
            + "\n".join(html_parts)
            + "</body></html>"
        )
        return ValidTextDocument(
            plain_text=plain_text,
            html=document_html,
            paragraph_anchors=paragraph_anchors,
        )

    def parse_paragraph_query(self, query: str) -> str | None:
        match = _PARAGRAPH_QUERY_RE.match((query or "").strip())
        if not match:
            return None
        return match.group(1).lower()

    def _append_section(
        self,
        section: LegalSection,
        *,
        children_by_parent: dict[int | None, list[LegalSection]],
        plain_parts: list[str],
        html_parts: list[str],
        paragraph_anchors: dict[str, str],
    ) -> None:
        section_type = (section.section_type or "").strip()

        if section_type in {SECTION_PART, SECTION_HEAD, SECTION_DIVISION}:
            heading = self._structure_heading(section)
            if heading:
                plain_parts.append(heading)
                html_parts.append(f"<h3>{html.escape(heading)}</h3>")
            for child in children_by_parent.get(section.id, []):
                self._append_section(
                    child,
                    children_by_parent=children_by_parent,
                    plain_parts=plain_parts,
                    html_parts=html_parts,
                    paragraph_anchors=paragraph_anchors,
                )
            return

        if section_type == SECTION_PARAGRAPH:
            block = legal_section_display_text_service.compose(section.id).strip()
            if not block:
                return
            paragraph = (section.paragraph or "").strip()
            anchor = f"p{paragraph.lower()}" if paragraph else None
            if paragraph:
                paragraph_anchors[paragraph.lower()] = anchor or ""
            plain_parts.append(block)
            html_parts.append(self._paragraph_block_to_html(block, anchor=anchor))
            return

        if section_type == SECTION_ATTACHMENT:
            title = (section.title or "").strip()
            text = (section.text or "").strip()
            block = self._join_blocks([part for part in [title, text] if part])
            if not block:
                return
            plain_parts.append(block)
            html_parts.append(self._plain_block_to_html(block))
            return

        block = legal_section_display_text_service.compose(section.id).strip()
        if block:
            plain_parts.append(block)
            html_parts.append(self._plain_block_to_html(block))

    def _structure_heading(self, section: LegalSection) -> str:
        section_type = (section.section_type or "").strip()
        number = (section.section_number or "").strip()
        title = (section.title or "").strip()

        if section_type == SECTION_PART:
            if number:
                return f"ČÁST {number}"
            return title or "ČÁST"
        if section_type == SECTION_HEAD:
            if number:
                return f"HLAVA {number}"
            return title or "HLAVA"
        if section_type == SECTION_DIVISION:
            if number:
                return f"Oddíl {number}"
            return title or "Oddíl"
        return title

    def _paragraph_block_to_html(self, text: str, *, anchor: str | None) -> str:
        parts: list[str] = []
        if anchor:
            parts.append(f'<a name="{html.escape(anchor)}"></a>')
        for line in text.splitlines():
            escaped = html.escape(line)
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("§"):
                parts.append(f"<p><b>{escaped}</b></p>")
            else:
                parts.append(f"<p>{escaped}</p>")
        return "\n".join(parts)

    def _plain_block_to_html(self, text: str) -> str:
        parts = [f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip()]
        return "\n".join(parts)

    def _join_blocks(self, blocks: list[str]) -> str:
        cleaned = [block.strip() for block in blocks if (block or "").strip()]
        return "\n\n".join(cleaned)


legal_document_valid_text_service = LegalDocumentValidTextService()
