from moduly.pravni_pozadavky.constants import (
    SECTION_LETTER,
    SECTION_PARAGRAPH,
    SECTION_SUBSECTION,
    VALID_SECTION_TYPES,
)
from moduly.pravni_pozadavky.modely.legal_section import LegalSection
from moduly.pravni_pozadavky.repository.legal_section_repository import LegalSectionRepository
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)


class LegalSectionService:
    def __init__(self):
        self.repository = LegalSectionRepository()

    def list_by_document(
        self,
        document_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        return self.repository.list_by_document(
            document_id,
            include_inactive=include_inactive,
        )

    def list_by_version(
        self,
        version_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        return self.repository.list_by_version(
            version_id,
            include_inactive=include_inactive,
        )

    def list_children(
        self,
        parent_section_id: int,
        *,
        include_inactive: bool = False,
    ) -> list[LegalSection]:
        return self.repository.list_children(
            parent_section_id,
            include_inactive=include_inactive,
        )

    def list_for_selector(
        self,
        *,
        document_id: int | None = None,
    ) -> list[LegalSection]:
        return self.repository.list_active(document_id=document_id)

    def get_by_id(self, section_id: int) -> LegalSection | None:
        return self.repository.get_by_id(section_id)

    def create(
        self,
        *,
        legal_document_id: int,
        legal_document_version_id: int,
        section_type: str,
        parent_section_id: int | None = None,
        section_number: str = "",
        paragraph: str = "",
        item_letter: str = "",
        title: str = "",
        text: str = "",
        sort_order: int = 0,
        note: str = "",
        active: bool = True,
    ) -> LegalSection:
        self._validate_document_id(legal_document_id)
        self._validate_version_id(legal_document_version_id)
        normalized_type = section_type.strip()
        self._validate_section_type(normalized_type)
        self._validate_content(
            normalized_type,
            section_number,
            paragraph,
            item_letter,
            title,
            text,
        )

        section = LegalSection(
            legal_document_id=legal_document_id,
            legal_document_version_id=legal_document_version_id,
            parent_section_id=parent_section_id,
            section_type=normalized_type,
            section_number=section_number.strip(),
            paragraph=paragraph.strip(),
            item_letter=item_letter.strip(),
            title=title.strip(),
            text=text.strip(),
            sort_order=sort_order,
            note=note.strip(),
            active=active,
        )
        return self.repository.create(section)

    def update(
        self,
        section_id: int,
        *,
        legal_document_id: int,
        legal_document_version_id: int,
        section_type: str,
        parent_section_id: int | None = None,
        section_number: str = "",
        paragraph: str = "",
        item_letter: str = "",
        title: str = "",
        text: str = "",
        sort_order: int = 0,
        note: str = "",
        active: bool = True,
    ) -> LegalSection | None:
        section = self.repository.get_by_id(section_id)
        if section is None:
            return None

        self._validate_document_id(legal_document_id)
        self._validate_version_id(legal_document_version_id)
        normalized_type = section_type.strip()
        self._validate_section_type(normalized_type)
        self._validate_content(
            normalized_type,
            section_number,
            paragraph,
            item_letter,
            title,
            text,
        )

        section.legal_document_id = legal_document_id
        section.legal_document_version_id = legal_document_version_id
        section.parent_section_id = parent_section_id
        section.section_type = normalized_type
        section.section_number = section_number.strip()
        section.paragraph = paragraph.strip()
        section.item_letter = item_letter.strip()
        section.title = title.strip()
        section.text = text.strip()
        section.sort_order = sort_order
        section.note = note.strip()
        section.active = active
        return self.repository.update(section)

    def deactivate(self, section_id: int) -> LegalSection | None:
        return self.repository.deactivate(section_id)

    def restore(self, section_id: int) -> LegalSection | None:
        return self.repository.restore(section_id)

    def _validate_document_id(self, legal_document_id: int) -> None:
        if not isinstance(legal_document_id, int) or legal_document_id <= 0:
            raise ValueError("Právní předpis je povinný.")
        if legal_document_service.get_by_id(legal_document_id) is None:
            raise ValueError("Právní předpis nebyl nalezen.")

    def _validate_version_id(self, legal_document_version_id: int) -> None:
        if not isinstance(legal_document_version_id, int) or legal_document_version_id <= 0:
            raise ValueError("Verze předpisu je povinná.")
        if legal_document_version_service.get_by_id(legal_document_version_id) is None:
            raise ValueError("Verze předpisu nebyla nalezena.")

    def _validate_section_type(self, section_type: str) -> None:
        if not section_type:
            raise ValueError("Typ části je povinný.")
        if section_type not in VALID_SECTION_TYPES:
            raise ValueError("Neplatný typ části.")

    def _validate_content(
        self,
        section_type: str,
        section_number: str,
        paragraph: str,
        item_letter: str,
        title: str,
        text: str,
    ) -> None:
        if section_type == SECTION_PARAGRAPH:
            if title.strip() or text.strip() or paragraph.strip():
                return
        elif section_type == SECTION_SUBSECTION:
            if section_number.strip() or text.strip():
                return
        elif section_type == SECTION_LETTER:
            if item_letter.strip() or text.strip():
                return
        elif section_number.strip() or title.strip() or text.strip():
            return
        raise ValueError("Vyplňte číslo, název nebo text části.")


legal_section_service = LegalSectionService()
