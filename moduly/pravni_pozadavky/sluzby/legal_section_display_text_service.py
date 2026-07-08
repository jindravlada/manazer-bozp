import re

from moduly.pravni_pozadavky.constants import (
    SECTION_ATTACHMENT,
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
)
from moduly.pravni_pozadavky.modely.legal_section import LegalSection
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

_NUMBERED_POINT_RE = re.compile(r"^\d+\.\s*")
_TECHNICAL_PARAGRAPH_TITLE_PREFIX = "(K §"


class LegalSectionDisplayTextService:
    def compose(self, section_id: int) -> str:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return ""

        section_type = (section.section_type or "").strip()
        if section_type == SECTION_ATTACHMENT:
            return (section.text or "").strip()

        own_text = (section.text or "").strip()
        has_descendants_with_text = self._subtree_has_text(section_id, skip_own_text=True)

        if own_text and not has_descendants_with_text:
            return own_text

        if section_type == SECTION_PARAGRAPH:
            return self._compose_paragraph(section, own_text)

        blocks: list[str] = []
        if own_text:
            blocks.append(own_text)
        blocks.extend(self._compose_children_blocks(section_id, depth=0))
        return self._join_blocks(blocks)

    def _compose_paragraph(self, section: LegalSection, own_text: str) -> str:
        child_blocks = self._compose_children_blocks(section.id, depth=0)
        intro_title = self._paragraph_intro_title(section)

        content_blocks: list[str] = []
        if own_text:
            content_blocks.append(own_text)
        elif intro_title:
            content_blocks.append(intro_title)
        content_blocks.extend(child_blocks)
        if not content_blocks:
            return ""

        blocks: list[str] = []
        paragraph = (section.paragraph or "").strip()
        if paragraph:
            blocks.append(f"§ {paragraph}")
        blocks.extend(content_blocks)
        return self._join_blocks(blocks)

    def _paragraph_intro_title(self, section: LegalSection) -> str:
        title = (section.title or "").strip()
        if not title or title.startswith(_TECHNICAL_PARAGRAPH_TITLE_PREFIX):
            return ""
        return title

    def _compose_children_blocks(self, parent_section_id: int, *, depth: int) -> list[str]:
        blocks: list[str] = []
        for child in legal_section_service.list_children(parent_section_id):
            block = self._compose_node_block(child, depth=depth)
            if block:
                blocks.append(block)
        return blocks

    def _compose_node_block(self, section: LegalSection, *, depth: int) -> str:
        section_type = (section.section_type or "").strip()
        own_text = (section.text or "").strip()
        child_blocks = self._compose_children_blocks(section.id, depth=depth + 1)

        if section_type == SECTION_SUBSECTION:
            number = (section.section_number or "").strip()
            header = f"({number}) {own_text}" if number else own_text
            if child_blocks:
                parts = [part for part in [header, *child_blocks] if part]
                return self._join_blocks(parts)
            return header

        if section_type == SECTION_LETTER:
            letter_block = self._format_letter_block(section, depth=depth)
            if child_blocks:
                parts = [part for part in [letter_block, *child_blocks] if part]
                return self._join_blocks(parts)
            return letter_block

        if own_text:
            indent = self._indent(depth)
            formatted = f"{indent}{own_text}" if indent else own_text
            if child_blocks:
                return self._join_blocks([formatted, *child_blocks])
            return formatted

        if child_blocks:
            return self._join_blocks(child_blocks)
        return ""

    def _format_letter_block(self, section: LegalSection, *, depth: int) -> str:
        letter = (section.item_letter or "").strip()
        text = (section.text or "").strip()
        if not letter and not text:
            return ""

        indent = self._indent(depth)
        body_indent = self._indent(depth + 1)

        intro_lines: list[str] = []
        body_lines: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _NUMBERED_POINT_RE.match(stripped):
                body_lines.append(stripped)
            else:
                intro_lines.append(stripped)

        lines: list[str] = []
        if intro_lines:
            first_line = f"{indent}{letter}) {intro_lines[0]}" if letter else f"{indent}{intro_lines[0]}"
            lines.append(first_line)
            for extra in intro_lines[1:]:
                lines.append(f"{indent}{extra}")
        elif letter:
            lines.append(f"{indent}{letter})")

        for body in body_lines:
            lines.append(f"{body_indent}{body}")

        return "\n".join(lines)

    def _subtree_has_text(self, section_id: int, *, skip_own_text: bool = False) -> bool:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return False

        if not skip_own_text and (section.text or "").strip():
            return True

        for child in legal_section_service.list_children(section_id):
            if self._subtree_has_text(child.id):
                return True
        return False

    def _indent(self, depth: int) -> str:
        if depth <= 0:
            return ""
        return " " * (4 * depth)

    def _join_blocks(self, blocks: list[str]) -> str:
        cleaned: list[str] = []
        for block in blocks:
            normalized = (block or "").rstrip()
            if normalized.strip():
                cleaned.append(normalized)
        return "\n\n".join(cleaned)


legal_section_display_text_service = LegalSectionDisplayTextService()
