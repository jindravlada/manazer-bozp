from datetime import datetime

from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
    HazardLibraryTemplateLegalLink,
)
from moduly.rizeni_rizik.repository.hazard_library_template_legal_link_repository import (
    HazardLibraryTemplateLegalLinkRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)


class HazardLibraryTemplateLegalLinkError(ValueError):
    pass


class HazardLibraryTemplateLegalLinkService:
    def __init__(self):
        self.repository = HazardLibraryTemplateLegalLinkRepository()

    def get_for_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardLibraryTemplateLegalLink]:
        return self.repository.get_for_template(
            template_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, link_id: int | None) -> HazardLibraryTemplateLegalLink | None:
        if not link_id:
            return None
        return self.repository.get_by_id(link_id)

    def create_link(
        self,
        *,
        template_id: int,
        legal_document_id: int,
        legal_requirement_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateLegalLink:
        """Vytvoří vazbu na právní předpis.

        ``legal_requirement_id`` se záměrně neukládá (R20e.1): proces se vždy
        dopočítává přes Zdroj → předpis → právní požadavky → Proces.
        """
        del legal_requirement_id  # API kompatibilita; nový zápis vazbu na proces/požadavek neukládá.
        self._validate_template(template_id)
        validated_document_id = self._validate_legal_document_id(legal_document_id)
        self._validate_unique_active_document(
            template_id,
            legal_document_id=validated_document_id,
            exclude_link_id=None,
            active=active,
        )

        link = HazardLibraryTemplateLegalLink(
            template_id=template_id,
            legal_document_id=validated_document_id,
            legal_requirement_id=None,
            note=note.strip(),
            active=active,
            sort_order=self.repository.next_sort_order(template_id),
        )
        return self.repository.add(link)

    def update_link(
        self,
        link_id: int,
        *,
        template_id: int,
        legal_document_id: int,
        legal_requirement_id: int | None = None,
        note: str = "",
        active: bool = True,
    ) -> HazardLibraryTemplateLegalLink | None:
        del legal_requirement_id
        link = self.repository.get_by_id(link_id)
        if link is None:
            return None

        self._validate_template(template_id)
        validated_document_id = self._validate_legal_document_id(legal_document_id)
        self._validate_unique_active_document(
            template_id,
            legal_document_id=validated_document_id,
            exclude_link_id=link_id,
            active=active,
        )

        link.template_id = template_id
        link.legal_document_id = validated_document_id
        link.legal_requirement_id = None
        link.note = note.strip()
        link.active = active
        link.updated_at = datetime.now()
        return self.repository.update(link)

    def activate_link(self, link_id: int) -> bool:
        link = self.repository.get_by_id(link_id)
        if link is None:
            return False
        if link.legal_document_id is None:
            raise HazardLibraryTemplateLegalLinkError(
                "Právní vazba nemá přiřazený právní předpis."
            )
        self._validate_unique_active_document(
            link.template_id,
            legal_document_id=link.legal_document_id,
            exclude_link_id=link_id,
            active=True,
        )
        link.active = True
        link.updated_at = datetime.now()
        self.repository.update(link)
        return True

    def deactivate_link(self, link_id: int) -> bool:
        link = self.repository.get_by_id(link_id)
        if link is None:
            return False
        link.active = False
        link.updated_at = datetime.now()
        self.repository.update(link)
        return True

    def _validate_template(self, template_id: int) -> None:
        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardLibraryTemplateLegalLinkError("Zdroj rizika neexistuje.")

    def _validate_legal_document_id(self, legal_document_id: int) -> int:
        document = legal_document_service.get_by_id(legal_document_id)
        if document is None:
            raise HazardLibraryTemplateLegalLinkError("Právní předpis neexistuje.")
        if not document.active:
            raise HazardLibraryTemplateLegalLinkError(
                "Právní předpis není aktivní a nelze ho použít ve vazbě."
            )
        return document.id

    def _validate_unique_active_document(
        self,
        template_id: int,
        *,
        legal_document_id: int,
        exclude_link_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        for link in self.get_for_template(template_id, include_inactive=True):
            if link.id == exclude_link_id:
                continue
            if not link.active:
                continue
            if link.legal_document_id == legal_document_id:
                raise HazardLibraryTemplateLegalLinkError(
                    "Tento právní předpis je u zdroje rizika již evidován."
                )


hazard_library_template_legal_link_service = HazardLibraryTemplateLegalLinkService()
