from moduly.pravni_pozadavky.constants import SECTION_LETTER, SECTION_SUBSECTION
from moduly.pravni_pozadavky.modely.legal_section import LegalSection
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalSectionDisplayTextService:
    def compose(self, section_id: int) -> str:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return ""

        own_text = (section.text or "").strip()
        if own_text:
            return own_text

        children = legal_section_service.list_children(section_id)
        parts: list[str] = []
        for child in children:
            child_text = self._compose_child_text(child)
            if child_text:
                parts.append(child_text)

        return "\n\n".join(parts)

    def _compose_child_text(self, section: LegalSection) -> str:
        text = (section.text or "").strip()
        if not text:
            return ""

        section_type = (section.section_type or "").strip()
        if section_type == SECTION_SUBSECTION:
            number = (section.section_number or "").strip()
            if number:
                return f"({number}) {text}"
            return text

        if section_type == SECTION_LETTER:
            letter = (section.item_letter or "").strip()
            if letter:
                return f"{letter}) {text}"
            return text

        return text


legal_section_display_text_service = LegalSectionDisplayTextService()
