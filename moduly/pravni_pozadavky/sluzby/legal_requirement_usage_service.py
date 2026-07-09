from dataclasses import dataclass

from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.pravni_pozadavky.constants import (
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.repository.legal_requirement_source_repository import (
    LegalRequirementSourceRepository,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


@dataclass(frozen=True)
class LegalProvisionUsage:
    label: str
    section_id: int


@dataclass(frozen=True)
class AuditAreaUsage:
    audit_process_name: str
    section_name: str

    @property
    def display_label(self) -> str:
        process_name = (self.audit_process_name or "").strip()
        section_name = (self.section_name or "").strip()
        if process_name and section_name:
            return f"{process_name} → {section_name}"
        if process_name:
            return process_name
        if section_name:
            return section_name
        return "—"


@dataclass(frozen=True)
class AuditAssertionUsage:
    text: str
    audit_process_name: str
    section_name: str


@dataclass(frozen=True)
class LegalRequirementUsage:
    legal_provisions: tuple[LegalProvisionUsage, ...]
    audit_areas: tuple[AuditAreaUsage, ...]
    audit_assertions: tuple[AuditAssertionUsage, ...]


class LegalRequirementUsageService:
    def __init__(self):
        self.source_repository = LegalRequirementSourceRepository()

    def get_usage(self, requirement_id: int) -> LegalRequirementUsage:
        legal_provisions = tuple(self._list_legal_provisions(requirement_id))
        audit_areas: list[AuditAreaUsage] = []
        audit_assertions: list[AuditAssertionUsage] = []

        for audit_process in audit_knowledge_service.get_processes(
            include_inactive=False,
            ensure=True,
        ):
            if not audit_process.has_knowledge_file:
                continue
            knowledge = audit_knowledge_service.load_process_knowledge(
                audit_process,
                ensure=False,
            )
            if knowledge is None:
                continue

            process_name = (
                str(knowledge.get("nazev") or audit_process.nazev or "").strip()
                or audit_process.id
            )
            self._collect_from_sections(
                knowledge.get("sekce") or [],
                requirement_id=requirement_id,
                audit_process_name=process_name,
                audit_areas=audit_areas,
                audit_assertions=audit_assertions,
            )

        audit_areas.sort(
            key=lambda item: (
                item.audit_process_name.casefold(),
                item.section_name.casefold(),
            ),
        )
        audit_assertions.sort(
            key=lambda item: (
                item.audit_process_name.casefold(),
                item.section_name.casefold(),
                item.text.casefold(),
            ),
        )

        return LegalRequirementUsage(
            legal_provisions=legal_provisions,
            audit_areas=tuple(audit_areas),
            audit_assertions=tuple(audit_assertions),
        )

    def _list_legal_provisions(self, requirement_id: int) -> list[LegalProvisionUsage]:
        provisions: list[LegalProvisionUsage] = []
        seen_section_ids: set[int] = set()

        for link in self.source_repository.list_by_requirement(requirement_id):
            section_id = link.legal_section_id
            if section_id in seen_section_ids:
                continue
            seen_section_ids.add(section_id)

            section = legal_section_service.get_by_id(section_id)
            if section is None or not section.active:
                continue

            document = legal_document_service.get_by_id(section.legal_document_id)
            label = self._build_legal_provision_label(document, section)
            if not label:
                continue

            provisions.append(
                LegalProvisionUsage(
                    label=label,
                    section_id=section_id,
                ),
            )

        provisions.sort(key=lambda item: item.label.casefold())
        return provisions

    def _build_legal_provision_label(self, document, section) -> str:
        document_number = legal_document_regulation_number(document) if document is not None else ""
        provision = legal_section_provision_label(section)
        if document_number and provision:
            return f"{document_number} {provision}"
        if provision:
            return provision
        return document_number

    def _collect_from_sections(
        self,
        sections: list,
        *,
        requirement_id: int,
        audit_process_name: str,
        audit_areas: list[AuditAreaUsage],
        audit_assertions: list[AuditAssertionUsage],
    ) -> None:
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("aktivni", True):
                continue

            section_name = str(section.get("nazev") or section.get("id") or "").strip()
            section_requirement_id = audit_knowledge_editor_service.normalize_legal_requirement_id(
                section.get("legal_requirement_id"),
            )
            if section_requirement_id == requirement_id:
                audit_areas.append(
                    AuditAreaUsage(
                        audit_process_name=audit_process_name,
                        section_name=section_name,
                    ),
                )
                raw_items = section.get("auditni_tvrzeni") or []
                active_items = audit_knowledge_service.get_active_items(raw_items)
                for item in audit_knowledge_service.normalize_auditni_tvrzeni(active_items):
                    text = str(item.get("text") or item.get("nazev") or "").strip()
                    if not text:
                        continue
                    audit_assertions.append(
                        AuditAssertionUsage(
                            text=text,
                            audit_process_name=audit_process_name,
                            section_name=section_name,
                        ),
                    )

            nested = section.get("sekce") or []
            if nested:
                self._collect_from_sections(
                    nested,
                    requirement_id=requirement_id,
                    audit_process_name=audit_process_name,
                    audit_areas=audit_areas,
                    audit_assertions=audit_assertions,
                )


legal_requirement_usage_service = LegalRequirementUsageService()
