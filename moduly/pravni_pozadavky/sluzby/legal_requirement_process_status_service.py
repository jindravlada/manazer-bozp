"""Aktuální stav řídicího procesu podle auditů, prověrek, právních požadavků a úkolů."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.shared.constants import (
    CONTROL_RESULT_LABELS,
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_AUDITY,
    ENTITY_LEGAL_REQUIREMENT,
    ENTITY_PROVERKY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    VALID_CONTROL_RESULTS,
)
from core.shared.control_result_display import CONTROL_RESULT_OPTIONS
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NENI_RELEVANTNI,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_SPLNENO,
    COMPLIANCE_STATUS_LABELS,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.ukoly.sluzby.task_service import task_service

PROCESS_STATUS_NO_ASSERTIONS = "Proces nemá přiřazena žádná auditní tvrzení."
PROCESS_STATUS_NOT_AUDITED = "Proces dosud nebyl ověřen dokončeným auditem."
PROCESS_STATUS_NO_INSPECTION_QUESTIONS = (
    "Proces nemá přiřazeny žádné kontrolní otázky prověrek."
)
PROCESS_STATUS_NOT_INSPECTED = (
    "Proces dosud nebyl ověřen žádnou dokončenou prověrkou."
)
PROCESS_STATUS_NO_LEGAL_REQUIREMENTS = (
    "K procesu nejsou přiřazeny žádné aktivní právní požadavky."
)
PROCESS_STATUS_UNEVALUATED_LABEL = "Bez vyhodnocení"
PROCESS_STATUS_NO_TASKS = "K procesu nejsou přiřazeny žádné aktivní úkoly."

TASK_STATUS_ACTIVE = "Aktivní"
TASK_STATUS_WAITING_CHECK = "Splněno - čeká na kontrolu"
TASK_STATUS_DONE = "Ukončeno"
TASK_STATUS_CANCELED = "Zrušeno"

_OPEN_TASK_STATUSES = frozenset(
    {
        TASK_STATUS_ACTIVE,
        TASK_STATUS_WAITING_CHECK,
    }
)
_TASK_STATUS_ORDER = (
    TASK_STATUS_ACTIVE,
    TASK_STATUS_WAITING_CHECK,
    TASK_STATUS_DONE,
    TASK_STATUS_CANCELED,
)

_COMPLIANCE_STATUS_ORDER = (
    COMPLIANCE_SPLNENO,
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_NENI_RELEVANTNI,
)

_OPEN_FINDING_STATUSES = frozenset(
    {
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
    }
)

# Váhy Indexu procesu (%) — součet aktivních oblastí musí být 100.
# Další oblasti (rizika, školení, …) se doplní zde bez změny UI.
PROCESS_INDEX_AREA_WEIGHTS: tuple[tuple[str, str, int], ...] = (
    ("audity", "Audity", 30),
    ("proverky", "Prověrky", 30),
    ("pravni_pozadavky", "Právní požadavky", 25),
    ("ukoly", "Úkoly", 15),
)

PROCESS_INDEX_PLACEHOLDER = "—"


@dataclass(frozen=True)
class LinkedAuditAssertionRef:
    process_id: str
    process_name: str
    section_id: str
    section_name: str
    assertion_id: str
    assertion_text: str


@dataclass(frozen=True)
class LinkedInspectionQuestionRef:
    area_id: str
    area_name: str
    section_id: str
    section_name: str
    question_id: str
    question_text: str


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
        return _format_entity_label(
            number=self.last_audit_number,
            title=self.last_audit_title,
            entity_id=self.last_audit_id,
            fallback_prefix="Audit",
        )


@dataclass(frozen=True)
class LegalRequirementProcessInspectionStatus:
    """Souhrn poslední dokončené prověrky pro řídicí proces."""

    question_count: int
    last_inspection_id: int | None = None
    last_inspection_date: date | None = None
    last_inspection_number: str = ""
    last_inspection_title: str = ""
    evaluated_count: int = 0
    result_counts: tuple[ProcessStatusResultCount, ...] = ()
    findings_total: int = 0
    findings_open: int = 0

    @property
    def empty_message(self) -> str | None:
        if self.question_count <= 0:
            return PROCESS_STATUS_NO_INSPECTION_QUESTIONS
        if self.last_inspection_id is None:
            return PROCESS_STATUS_NOT_INSPECTED
        return None

    @property
    def last_inspection_label(self) -> str:
        return _format_entity_label(
            number=self.last_inspection_number,
            title=self.last_inspection_title,
            entity_id=self.last_inspection_id,
            fallback_prefix="Prověrka",
        )


@dataclass(frozen=True)
class LegalRequirementProcessLegalStatus:
    """Souhrn aktivních podřízených právních požadavků řídicího procesu."""

    requirement_count: int
    status_counts: tuple[ProcessStatusResultCount, ...] = ()

    @property
    def empty_message(self) -> str | None:
        if self.requirement_count <= 0:
            return PROCESS_STATUS_NO_LEGAL_REQUIREMENTS
        return None


@dataclass(frozen=True)
class LegalRequirementProcessTaskStatus:
    """Souhrn úkolů přímo navázaných na řídicí proces."""

    task_count: int
    open_count: int = 0
    overdue_open_count: int = 0
    nearest_due_date: date | None = None
    status_counts: tuple[ProcessStatusResultCount, ...] = ()

    @property
    def empty_message(self) -> str | None:
        if self.task_count <= 0:
            return PROCESS_STATUS_NO_TASKS
        return None


@dataclass(frozen=True)
class ProcessIndexAreaBreakdown:
    """Jedna oblast rozpadu budoucího Indexu procesu."""

    area_id: str
    area_label: str
    weight_percent: int
    score: float | None = None
    contribution: float | None = None


@dataclass(frozen=True)
class ProcessIndexBreakdown:
    """Rozpad Indexu procesu — váhy nyní, skóre a index později."""

    areas: tuple[ProcessIndexAreaBreakdown, ...]
    total_weight_percent: int
    index_value: float | None = None


def _format_entity_label(
    *,
    number: str,
    title: str,
    entity_id: int | None,
    fallback_prefix: str,
) -> str:
    number = (number or "").strip()
    title = (title or "").strip()
    if number and title and number != title:
        return f"{number} — {title}"
    if number:
        return number
    if title:
        return title
    if entity_id is not None:
        return f"{fallback_prefix} {entity_id}"
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

        last_audit = self._find_last_completed_entity_with_evaluation(
            entities=audit_service.get_all(),
            entity_type=ENTITY_AUDITY,
            keys=assertion_keys,
            control_point_ids=assertion_ids,
            finished_at_attr="finished_at",
            secondary_date_attr="audit_date",
        )
        if last_audit is None:
            return LegalRequirementProcessAuditStatus(assertion_count=len(assertions))

        matching_results = self._matching_results_for_entity(
            entity_type=ENTITY_AUDITY,
            entity_id=last_audit.id,
            keys=assertion_keys,
            control_point_ids=assertion_ids,
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

    def get_inspection_status(
        self,
        requirement_id: int,
    ) -> LegalRequirementProcessInspectionStatus:
        questions = self._list_linked_inspection_questions(requirement_id)
        if not questions:
            return LegalRequirementProcessInspectionStatus(question_count=0)

        question_keys = {
            (item.area_id, item.section_id, item.question_id)
            for item in questions
            if item.question_id
        }
        question_ids = {item.question_id for item in questions if item.question_id}
        label_keys = {
            (item.area_name, item.section_name, item.question_id)
            for item in questions
            if item.question_id
        }

        last_inspection = self._find_last_completed_entity_with_evaluation(
            entities=bozp_inspection_service.get_all(),
            entity_type=ENTITY_PROVERKY,
            keys=question_keys,
            control_point_ids=question_ids,
            finished_at_attr="finished_at",
            secondary_date_attr="inspection_date",
        )
        if last_inspection is None:
            return LegalRequirementProcessInspectionStatus(question_count=len(questions))

        matching_results = self._matching_results_for_entity(
            entity_type=ENTITY_PROVERKY,
            entity_id=last_inspection.id,
            keys=question_keys,
            control_point_ids=question_ids,
        )
        counts = self._count_results(matching_results)
        evaluated_count = sum(
            item.count
            for item in counts
            if item.result_code != CONTROL_RESULT_NEKONTROLOVANO
        )
        findings_total, findings_open = self._count_findings_for_questions(
            inspection_id=last_inspection.id,
            label_keys=label_keys,
            question_ids=question_ids,
        )

        return LegalRequirementProcessInspectionStatus(
            question_count=len(questions),
            last_inspection_id=last_inspection.id,
            last_inspection_date=(
                last_inspection.finished_at or last_inspection.inspection_date
            ),
            last_inspection_number=str(last_inspection.number or "").strip(),
            last_inspection_title=str(last_inspection.title or "").strip(),
            evaluated_count=evaluated_count,
            result_counts=counts,
            findings_total=findings_total,
            findings_open=findings_open,
        )

    def get_legal_requirements_status(
        self,
        requirement_id: int,
    ) -> LegalRequirementProcessLegalStatus:
        children = legal_requirement_service.list_children(requirement_id)
        if not children:
            return LegalRequirementProcessLegalStatus(requirement_count=0)

        counts: dict[str, int] = {code: 0 for code in _COMPLIANCE_STATUS_ORDER}
        unevaluated = 0
        for child in children:
            code = str(child.compliance_status or "").strip()
            if code in counts:
                counts[code] += 1
            else:
                unevaluated += 1

        status_counts = tuple(
            ProcessStatusResultCount(
                result_code=code,
                result_label=COMPLIANCE_STATUS_LABELS[code],
                count=counts[code],
            )
            for code in _COMPLIANCE_STATUS_ORDER
        ) + (
            ProcessStatusResultCount(
                result_code="",
                result_label=PROCESS_STATUS_UNEVALUATED_LABEL,
                count=unevaluated,
            ),
        )
        return LegalRequirementProcessLegalStatus(
            requirement_count=len(children),
            status_counts=status_counts,
        )

    def get_task_status(self, requirement_id: int) -> LegalRequirementProcessTaskStatus:
        tasks = [
            task
            for task in task_service.get_all_tasks()
            if (
                str(task.source_module or "").strip() == ENTITY_LEGAL_REQUIREMENT
                and task.source_record_id == requirement_id
            )
        ]
        if not tasks:
            return LegalRequirementProcessTaskStatus(task_count=0)

        status_totals: dict[str, int] = {label: 0 for label in _TASK_STATUS_ORDER}
        open_count = 0
        overdue_open_count = 0
        nearest_due: date | None = None
        today = date.today()

        for task in tasks:
            status = str(task.computed_status or "").strip() or TASK_STATUS_ACTIVE
            if status not in status_totals:
                status_totals[status] = 0
            status_totals[status] += 1

            if status not in _OPEN_TASK_STATUSES:
                continue

            open_count += 1
            due_date = task.due_date
            if due_date is None:
                continue
            if due_date < today:
                overdue_open_count += 1
            if nearest_due is None or due_date < nearest_due:
                nearest_due = due_date

        status_counts = tuple(
            ProcessStatusResultCount(
                result_code=label,
                result_label=label,
                count=status_totals.get(label, 0),
            )
            for label in _TASK_STATUS_ORDER
        )
        for label, count in status_totals.items():
            if label in _TASK_STATUS_ORDER:
                continue
            status_counts = status_counts + (
                ProcessStatusResultCount(
                    result_code=label,
                    result_label=label,
                    count=count,
                ),
            )

        return LegalRequirementProcessTaskStatus(
            task_count=len(tasks),
            open_count=open_count,
            overdue_open_count=overdue_open_count,
            nearest_due_date=nearest_due,
            status_counts=status_counts,
        )

    def get_process_index_breakdown(
        self,
        requirement_id: int | None = None,
    ) -> ProcessIndexBreakdown:
        """Vrátí rozpad oblastí Indexu procesu (váhy pevné, skóre zatím prázdné)."""
        _ = requirement_id  # výpočet skóre přijde v další fázi
        areas = tuple(
            ProcessIndexAreaBreakdown(
                area_id=area_id,
                area_label=area_label,
                weight_percent=weight_percent,
                score=None,
                contribution=None,
            )
            for area_id, area_label, weight_percent in PROCESS_INDEX_AREA_WEIGHTS
        )
        total_weight = sum(item.weight_percent for item in areas)
        return ProcessIndexBreakdown(
            areas=areas,
            total_weight_percent=total_weight,
            index_value=None,
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
                self._collect_assertions_from_sections(
                    knowledge.get("sekce") or [],
                    requirement_id=requirement_id,
                    process_id=audit_process.id,
                    process_name=process_name,
                ),
            )
        return collected

    def _collect_assertions_from_sections(
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
                    self._collect_assertions_from_sections(
                        nested,
                        requirement_id=requirement_id,
                        process_id=process_id,
                        process_name=process_name,
                    ),
                )
        return collected

    def _list_linked_inspection_questions(
        self,
        requirement_id: int,
    ) -> list[LinkedInspectionQuestionRef]:
        collected: list[LinkedInspectionQuestionRef] = []
        try:
            areas = proverky_knowledge_service.get_areas(include_inactive=False)
        except Exception:
            return collected

        for area in areas:
            if not area.has_knowledge_file:
                continue
            try:
                knowledge = proverky_knowledge_service.load_area_knowledge(area)
            except Exception:
                continue
            if knowledge is None:
                continue

            area_name = str(knowledge.get("nazev") or area.nazev or "").strip() or area.id
            collected.extend(
                self._collect_questions_from_sections(
                    knowledge.get("sekce") or [],
                    requirement_id=requirement_id,
                    area_id=area.id,
                    area_name=area_name,
                ),
            )
        return collected

    def _collect_questions_from_sections(
        self,
        sections: list,
        *,
        requirement_id: int,
        area_id: str,
        area_name: str,
    ) -> list[LinkedInspectionQuestionRef]:
        collected: list[LinkedInspectionQuestionRef] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            if not section.get("aktivni", True):
                continue

            section_id = str(section.get("id") or "").strip()
            section_name = str(section.get("nazev") or section_id).strip()
            section_requirement_id = proverky_knowledge_service.normalize_legal_requirement_id(
                section.get("legal_requirement_id"),
            )
            if section_requirement_id == requirement_id:
                raw_items = section.get("kontrolni_body") or []
                active_items = proverky_knowledge_service.get_active_items(raw_items)
                for item in proverky_knowledge_service.normalize_kontrolni_body(active_items):
                    question_id = str(item.get("id") or "").strip()
                    text = str(item.get("nazev") or "").strip()
                    if not question_id or not text:
                        continue
                    collected.append(
                        LinkedInspectionQuestionRef(
                            area_id=area_id,
                            area_name=area_name,
                            section_id=section_id,
                            section_name=section_name,
                            question_id=question_id,
                            question_text=text,
                        ),
                    )

            nested = section.get("sekce") or []
            if nested:
                collected.extend(
                    self._collect_questions_from_sections(
                        nested,
                        requirement_id=requirement_id,
                        area_id=area_id,
                        area_name=area_name,
                    ),
                )
        return collected

    def _find_last_completed_entity_with_evaluation(
        self,
        *,
        entities: list,
        entity_type: str,
        keys: set[tuple[str, str, str]],
        control_point_ids: set[str],
        finished_at_attr: str,
        secondary_date_attr: str,
    ):
        best = None
        best_key: tuple[date, date, int] | None = None

        for entity in entities:
            finished_at = getattr(entity, finished_at_attr, None)
            if finished_at is None:
                continue
            matching = self._matching_results_for_entity(
                entity_type=entity_type,
                entity_id=entity.id,
                keys=keys,
                control_point_ids=control_point_ids,
            )
            if not any(row.result != CONTROL_RESULT_NEKONTROLOVANO for row in matching):
                continue

            secondary = getattr(entity, secondary_date_attr, None) or finished_at
            sort_key = (finished_at, secondary, entity.id)
            if best_key is None or sort_key > best_key:
                best = entity
                best_key = sort_key

        return best

    def _matching_results_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: int,
        keys: set[tuple[str, str, str]],
        control_point_ids: set[str],
    ) -> list:
        matching = []
        for row in control_result_service.get_for_entity(entity_type, entity_id):
            if self._result_matches_linked_control_point(
                row,
                keys=keys,
                control_point_ids=control_point_ids,
            ):
                matching.append(row)
        return matching

    @staticmethod
    def _result_matches_linked_control_point(
        row,
        *,
        keys: set[tuple[str, str, str]],
        control_point_ids: set[str],
    ) -> bool:
        control_point_id = str(row.source_control_point_id or "").strip()
        if not control_point_id or control_point_id not in control_point_ids:
            return False

        area_id = str(row.source_area_id or "").strip()
        section_id = str(row.source_section_id or "").strip()
        if area_id and section_id:
            return (area_id, section_id, control_point_id) in keys

        # Starší záznamy bez ID oblasti/sekce: stačí shoda ID bodu.
        return True

    def _count_findings_for_questions(
        self,
        *,
        inspection_id: int,
        label_keys: set[tuple[str, str, str]],
        question_ids: set[str],
    ) -> tuple[int, int]:
        total = 0
        open_count = 0
        for finding in finding_service.get_for_entity(ENTITY_PROVERKY, inspection_id):
            control_point_id = str(finding.source_control_point_id or "").strip()
            if not control_point_id or control_point_id not in question_ids:
                continue

            area_label = str(finding.source_area_label or "").strip()
            section_label = str(finding.source_section_label or "").strip()
            if area_label and section_label:
                if (area_label, section_label, control_point_id) not in label_keys:
                    continue

            total += 1
            if str(finding.status or "").strip() in _OPEN_FINDING_STATUSES:
                open_count += 1
        return total, open_count

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
