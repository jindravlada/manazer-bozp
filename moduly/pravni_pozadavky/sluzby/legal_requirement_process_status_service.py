"""Aktuální stav řídicího procesu podle existujících výsledků auditů."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.shared.constants import (
    CONTROL_RESULT_LABELS,
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_AUDITY,
    VALID_CONTROL_RESULTS,
)
from core.shared.control_result_display import CONTROL_RESULT_OPTIONS
from core.shared.sluzby.control_result_service import control_result_service
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_service import audit_service

PROCESS_STATUS_NO_ASSERTIONS = "Proces nemá přiřazena žádná auditní tvrzení."
PROCESS_STATUS_NOT_AUDITED = "Proces dosud nebyl ověřen dokončeným auditem."


@dataclass(frozen=True)
class LinkedAuditAssertionRef:
    process_id: str
    process_name: str
    section_id: str
    section_name: str
    assertion_id: str
    assertion_text: str


@dataclass(frozen=True)
class ProcessStatusResultCount:
    result_code: str
    result_label: str
    count: int


@dataclass(frozen=True)
class LegalRequirementProcessAuditStatus:
    """Souhrn posledního dokončeného auditu pro řídicí proces."""

    assertion_count: int
    last_audit_id: int | None = None
    last_audit_date: date | None = None
    last_audit_number: str = ""
    last_audit_title: str = ""
    evaluated_count: int = 0
    result_counts: tuple[ProcessStatusResultCount, ...] = ()

    @property
    def empty_message(self) -> str | None:
        if self.assertion_count <= 0:
            return PROCESS_STATUS_NO_ASSERTIONS
        if self.last_audit_id is None:
            return PROCESS_STATUS_NOT_AUDITED
        return None

    @property
    def last_audit_label(self) -> str:
        number = (self.last_audit_number or "").strip()
        title = (self.last_audit_title or "").strip()
        if number and title and number != title:
            return f"{number} — {title}"
        if number:
            return number
        if title:
            return title
        if self.last_audit_id is not None:
            return f"Audit {self.last_audit_id}"
        return ""


class LegalRequirementProcessStatusService:
    def get_audit_status(self, requirement_id: int) -> LegalRequirementProcessAuditStatus:
        assertions = self._list_linked_assertions(requirement_id)
        if not assertions:
            return LegalRequirementProcessAuditStatus(assertion_count=0)

        assertion_keys = {
            (item.process_id, item.section_id, item.assertion_id)
            for item in assertions
            if item.assertion_id
        }
        assertion_ids = {item.assertion_id for item in assertions if item.assertion_id}

        last_audit = self._find_last_completed_audit_with_evaluation(
            assertion_keys=assertion_keys,
            assertion_ids=assertion_ids,
        )
        if last_audit is None:
            return LegalRequirementProcessAuditStatus(assertion_count=len(assertions))

        matching_results = self._matching_results_for_audit(
            audit_id=last_audit.id,
            assertion_keys=assertion_keys,
            assertion_ids=assertion_ids,
        )
        counts = self._count_results(matching_results)
        evaluated_count = sum(
            item.count
            for item in counts
            if item.result_code != CONTROL_RESULT_NEKONTROLOVANO
        )

        return LegalRequirementProcessAuditStatus(
            assertion_count=len(assertions),
            last_audit_id=last_audit.id,
            last_audit_date=last_audit.finished_at or last_audit.audit_date,
            last_audit_number=str(last_audit.number or "").strip(),
            last_audit_title=str(last_audit.title or "").strip(),
            evaluated_count=evaluated_count,
            result_counts=counts,
        )

    def _list_linked_assertions(self, requirement_id: int) -> list[LinkedAuditAssertionRef]:
        collected: list[LinkedAuditAssertionRef] = []
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
            collected.extend(
                self._collect_from_sections(
                    knowledge.get("sekce") or [],
                    requirement_id=requirement_id,
                    process_id=audit_process.id,
                    process_name=process_name,
                ),
            )
        return collected

    def _collect_from_sections(
        self,
        sections: list,
        *,
        requirement_id: int,
        process_id: str,
        process_name: str,
    ) -> list[LinkedAuditAssertionRef]:
        collected: list[LinkedAuditAssertionRef] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("aktivni", True):
                continue

            section_id = str(section.get("id") or "").strip()
            section_name = str(section.get("nazev") or section_id).strip()
            section_requirement_id = audit_knowledge_editor_service.normalize_legal_requirement_id(
                section.get("legal_requirement_id"),
            )
            if section_requirement_id == requirement_id:
                raw_items = section.get("auditni_tvrzeni") or []
                active_items = audit_knowledge_service.get_active_items(raw_items)
                for item in audit_knowledge_service.normalize_auditni_tvrzeni(active_items):
                    assertion_id = str(item.get("id") or "").strip()
                    text = str(item.get("text") or item.get("nazev") or "").strip()
                    if not assertion_id or not text:
                        continue
                    collected.append(
                        LinkedAuditAssertionRef(
                            process_id=process_id,
                            process_name=process_name,
                            section_id=section_id,
                            section_name=section_name,
                            assertion_id=assertion_id,
                            assertion_text=text,
                        ),
                    )

            nested = section.get("sekce") or []
            if nested:
                collected.extend(
                    self._collect_from_sections(
                        nested,
                        requirement_id=requirement_id,
                        process_id=process_id,
                        process_name=process_name,
                    ),
                )
        return collected

    def _find_last_completed_audit_with_evaluation(
        self,
        *,
        assertion_keys: set[tuple[str, str, str]],
        assertion_ids: set[str],
    ):
        best = None
        best_key: tuple[date, date, int] | None = None

        for audit in audit_service.get_all():
            if audit.finished_at is None:
                continue
            matching = self._matching_results_for_audit(
                audit_id=audit.id,
                assertion_keys=assertion_keys,
                assertion_ids=assertion_ids,
            )
            if not any(row.result != CONTROL_RESULT_NEKONTROLOVANO for row in matching):
                continue

            sort_key = (
                audit.finished_at,
                audit.audit_date or audit.finished_at,
                audit.id,
            )
            if best_key is None or sort_key > best_key:
                best = audit
                best_key = sort_key

        return best

    def _matching_results_for_audit(
        self,
        *,
        audit_id: int,
        assertion_keys: set[tuple[str, str, str]],
        assertion_ids: set[str],
    ) -> list:
        matching = []
        for row in control_result_service.get_for_entity(ENTITY_AUDITY, audit_id):
            if self._result_matches_linked_assertion(
                row,
                assertion_keys=assertion_keys,
                assertion_ids=assertion_ids,
            ):
                matching.append(row)
        return matching

    @staticmethod
    def _result_matches_linked_assertion(
        row,
        *,
        assertion_keys: set[tuple[str, str, str]],
        assertion_ids: set[str],
    ) -> bool:
        control_point_id = str(row.source_control_point_id or "").strip()
        if not control_point_id or control_point_id not in assertion_ids:
            return False

        area_id = str(row.source_area_id or "").strip()
        section_id = str(row.source_section_id or "").strip()
        if area_id and section_id:
            return (area_id, section_id, control_point_id) in assertion_keys

        # Starší záznamy bez ID oblasti/sekce: stačí shoda ID tvrzení.
        return True

    def _count_results(self, results: list) -> tuple[ProcessStatusResultCount, ...]:
        counts: dict[str, int] = {code: 0 for code, _label in CONTROL_RESULT_OPTIONS}
        for row in results:
            code = str(row.result or "").strip()
            if code not in counts:
                counts[code] = 0
            counts[code] += 1

        ordered: list[ProcessStatusResultCount] = []
        for code, label in CONTROL_RESULT_OPTIONS:
            ordered.append(
                ProcessStatusResultCount(
                    result_code=code,
                    result_label=label,
                    count=counts.get(code, 0),
                ),
            )
        for code, count in counts.items():
            if code in VALID_CONTROL_RESULTS:
                continue
            ordered.append(
                ProcessStatusResultCount(
                    result_code=code,
                    result_label=CONTROL_RESULT_LABELS.get(code, code),
                    count=count,
                ),
            )
        return tuple(ordered)


legal_requirement_process_status_service = LegalRequirementProcessStatusService()
