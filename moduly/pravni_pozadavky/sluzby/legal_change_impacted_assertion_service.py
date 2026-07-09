import re
import unicodedata
from dataclasses import dataclass

from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.pravni_pozadavky.constants import process_code_sort_key
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
    ImpactedControlProcess,
    legal_change_impacted_process_service,
)

_LABEL_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ImpactedAuditAssertion:
    assertion_id: str
    assertion_order: int | None
    text: str
    process_code: str
    process_name: str

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


class LegalChangeImpactedAssertionService:
    def list_assertions_for_change(self, legal_change_id: int) -> list[ImpactedAuditAssertion]:
        processes = legal_change_impacted_process_service.list_processes_for_change(legal_change_id)
        if not processes:
            return []

        assertions: list[ImpactedAuditAssertion] = []
        seen_keys: set[tuple[str, str]] = set()

        for process in sorted(processes, key=self._process_sort_key):
            for assertion in self._list_assertions_for_process(process):
                key = (process.process_code, assertion.assertion_id)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                assertions.append(assertion)

        assertions.sort(
            key=lambda item: (
                self._process_sort_key_from_fields(item.process_code, item.process_name),
                item.assertion_order if item.assertion_order is not None else 0,
                item.assertion_id.lower(),
                item.text.lower(),
            ),
        )
        return assertions

    def _list_assertions_for_process(
        self,
        process: ImpactedControlProcess,
    ) -> list[ImpactedAuditAssertion]:
        audit_process = self._resolve_audit_process(process.process_name)
        if audit_process is None or not audit_process.has_knowledge_file:
            return []

        knowledge = audit_knowledge_service.load_process_knowledge(audit_process)
        if knowledge is None:
            return []

        raw_assertions = self._collect_assertions_from_sections(knowledge.get("sekce") or [])
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
            assertions.append(
                ImpactedAuditAssertion(
                    assertion_id=assertion_id,
                    assertion_order=assertion_order,
                    text=text,
                    process_code=process.process_code,
                    process_name=process.process_name,
                ),
            )
        return assertions

    def _resolve_audit_process(self, process_name: str):
        normalized = self._normalize_label(process_name)
        if not normalized:
            return None

        for process in audit_knowledge_service.get_processes(include_inactive=False, ensure=True):
            if self._normalize_label(process.nazev) == normalized:
                return process

            if not process.has_knowledge_file:
                continue
            knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
            if knowledge is None:
                continue
            knowledge_name = str(knowledge.get("nazev") or "").strip()
            if self._normalize_label(knowledge_name) == normalized:
                return process
        return None

    def _collect_assertions_from_sections(self, sections: list) -> list[dict]:
        collected: list[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("aktivni", True):
                continue

            raw_items = section.get("auditni_tvrzeni") or []
            active_items = audit_knowledge_service.get_active_items(raw_items)
            collected.extend(audit_knowledge_service.normalize_auditni_tvrzeni(active_items))

            nested = section.get("sekce") or []
            if nested:
                collected.extend(self._collect_assertions_from_sections(nested))
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

    def _normalize_label(self, label: str) -> str:
        normalized = unicodedata.normalize("NFKD", (label or "").strip().casefold())
        ascii_text = "".join(
            character for character in normalized if not unicodedata.combining(character)
        )
        ascii_text = _LABEL_RE.sub(" ", ascii_text)
        return ascii_text.strip()


legal_change_impacted_assertion_service = LegalChangeImpactedAssertionService()
