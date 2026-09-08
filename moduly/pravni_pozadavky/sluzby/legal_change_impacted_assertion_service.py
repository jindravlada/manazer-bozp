from dataclasses import dataclass

from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.pravni_pozadavky.constants import (
    CHANGE_SECTION_TYPE_LABELS,
    process_code_sort_key,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
    ImpactedControlProcess,
    ImpactedProcessLegalSource,
    legal_change_impacted_process_service,
)


@dataclass(frozen=True)
class ImpactedAuditAssertion:
    assertion_id: str
    assertion_order: int | None
    text: str
    process_code: str
    process_name: str
    section_id: int
    section_label: str
    change_type: str

    @property
    def process_display(self) -> str:
        code = (self.process_code or "").strip()
        name = (self.process_name or "").strip()
        if code and name:
            return f"{code} {name}"
        if code:
            return code
        if name:
            return name
        return "—"

    @property
    def code_or_order_label(self) -> str:
        code = (self.assertion_id or "").strip()
        if code:
            return code
        if self.assertion_order is not None:
            return str(self.assertion_order)
        return "—"

    @property
    def change_type_label(self) -> str:
        return CHANGE_SECTION_TYPE_LABELS.get(self.change_type, self.change_type)


class LegalChangeImpactedAssertionService:
    def list_assertions_for_change(self, legal_change_id: int) -> list[ImpactedAuditAssertion]:
        processes = legal_change_impacted_process_service.list_processes_for_change(legal_change_id)
        if not processes:
            return []

        assertions: list[ImpactedAuditAssertion] = []
        seen_keys: set[tuple[str, str, int]] = set()

        for process in sorted(processes, key=self._process_sort_key):
            for assertion in self._list_assertions_for_process(process):
                key = (process.process_code, assertion.assertion_id, assertion.section_id)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                assertions.append(assertion)

        assertions.sort(
            key=lambda item: (
                self._process_sort_key_from_fields(item.process_code, item.process_name),
                item.assertion_order if item.assertion_order is not None else 0,
                item.assertion_id.lower(),
                item.section_label.lower(),
                item.text.lower(),
            ),
        )
        return assertions

    def _list_assertions_for_process(
        self,
        process: ImpactedControlProcess,
    ) -> list[ImpactedAuditAssertion]:
        raw_assertions = self._collect_assertions_for_requirement(process.requirement_id)
        assertions: list[ImpactedAuditAssertion] = []
        for raw in raw_assertions:
            text = str(raw.get("text") or raw.get("nazev") or "").strip()
            if not text:
                continue
            assertion_id = str(raw.get("id") or "").strip()
            poradi = raw.get("poradi")
            try:
                assertion_order = int(poradi) if poradi is not None else None
            except (TypeError, ValueError):
                assertion_order = None
            for source in process.legal_sources:
                assertions.append(
                    self._build_assertion(
                        assertion_id=assertion_id,
                        assertion_order=assertion_order,
                        text=text,
                        process=process,
                        source=source,
                    ),
                )
        return assertions

    def _build_assertion(
        self,
        *,
        assertion_id: str,
        assertion_order: int | None,
        text: str,
        process: ImpactedControlProcess,
        source: ImpactedProcessLegalSource,
    ) -> ImpactedAuditAssertion:
        return ImpactedAuditAssertion(
            assertion_id=assertion_id,
            assertion_order=assertion_order,
            text=text,
            process_code=process.process_code,
            process_name=process.process_name,
            section_id=source.section_id,
            section_label=source.label,
            change_type=source.change_type,
        )

    def _collect_assertions_for_requirement(self, requirement_id: int) -> list[dict]:
        collected: list[dict] = []
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
            collected.extend(
                self._collect_assertions_from_linked_sections(
                    knowledge.get("sekce") or [],
                    requirement_id=requirement_id,
                ),
            )
        return collected

    def _collect_assertions_from_linked_sections(
        self,
        sections: list,
        *,
        requirement_id: int,
    ) -> list[dict]:
        collected: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("aktivni", True):
                continue

            section_requirement_id = audit_knowledge_editor_service.normalize_legal_requirement_id(
                section.get("legal_requirement_id"),
            )
            if section_requirement_id == requirement_id:
                raw_items = section.get("auditni_tvrzeni") or []
                active_items = audit_knowledge_service.get_active_items(raw_items)
                collected.extend(
                    audit_knowledge_service.normalize_auditni_tvrzeni(active_items),
                )

            nested = section.get("sekce") or []
            if nested:
                collected.extend(
                    self._collect_assertions_from_linked_sections(
                        nested,
                        requirement_id=requirement_id,
                    ),
                )
        return collected

    def _process_sort_key(self, process: ImpactedControlProcess) -> tuple:
        return self._process_sort_key_from_fields(process.process_code, process.process_name)

    def _process_sort_key_from_fields(self, process_code: str, process_name: str) -> tuple:
        requirement = LegalRequirement(
            id=0,
            title=process_name,
            process_code=process_code,
        )
        return process_code_sort_key(requirement)


legal_change_impacted_assertion_service = LegalChangeImpactedAssertionService()
