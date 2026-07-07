from moduly.pravni_pozadavky.constants import (
    DEFAULT_PROCESSING_STATUS,
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRequirementCreationService:
    def create_from_section(self, section_id: int) -> LegalRequirement:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            raise ValueError("Ustanovení předpisu nebylo nalezeno.")

        document = legal_document_service.get_by_id(section.legal_document_id)
        regulation_number = ""
        if document is not None:
            regulation_number = legal_document_regulation_number(document)

        regulation_name = ""
        if document is not None:
            regulation_name = document.title.strip()

        sections_by_id = legal_section_service.build_sections_map([section])

        return LegalRequirement(
            legal_document_id=section.legal_document_id,
            legal_section_id=section.id,
            source_section_id=section.id,
            regulation_name=regulation_name,
            regulation_number=regulation_number,
            provision=legal_section_provision_label(section, sections_by_id=sections_by_id),
            requirement_summary="",
            processing_status=DEFAULT_PROCESSING_STATUS,
            active=True,
        )


legal_requirement_creation_service = LegalRequirementCreationService()
