from dataclasses import dataclass
from datetime import date, datetime

from core.shared.constants import ENTITY_PROVERKY
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.finding_service import finding_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.proverky.constants import (
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except Exception:
        return text


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


_COMMISSION_ROLE_LABELS = {
    COMMISSION_RECORD_LEADER: "Vedoucí komise",
    COMMISSION_RECORD_WORKPLACE: "Zástupce pracoviště",
    COMMISSION_RECORD_UNION: "Zástupce odborové organizace",
    COMMISSION_RECORD_MEMBER: "Člen komise",
    COMMISSION_RECORD_INVITED: "Přizvaná osoba",
}

_COMMISSION_EXPORT_ORDER = {
    COMMISSION_RECORD_LEADER: 1,
    COMMISSION_RECORD_WORKPLACE: 2,
    COMMISSION_RECORD_UNION: 3,
    COMMISSION_RECORD_MEMBER: 4,
    COMMISSION_RECORD_INVITED: 5,
}


@dataclass(frozen=True)
class InspectionExportContext:
    """Sjednocený kontext exportu protokolu prověrky BOZP."""

    inspection: BozpInspection

    @property
    def inspection_id(self) -> int:
        return self.inspection.id

    def is_completed(self) -> bool:
        return self.inspection.finished_at is not None

    def planned_month_label(self) -> str:
        month = self.inspection.planned_month
        if month is None or month < 1 or month > 12:
            return PLANNED_MONTH_NOT_SET_LABEL
        return PLANNED_MONTH_NAMES[month - 1]

    def status_label(self) -> str:
        return bozp_inspection_service.derive_status(
            self.inspection.started_at,
            self.inspection.finished_at,
        )

    def employer_name(self) -> str:
        employer = settings_service.get_employer()
        if employer is None:
            return ""
        return _text(employer.name)

    def commission_lines(self) -> list[str]:
        members = bozp_inspection_commission_service.get_for_inspection(self.inspection_id)
        if not members:
            return []

        lines: list[str] = []
        for member in sorted(
            members,
            key=lambda item: (
                _COMMISSION_EXPORT_ORDER.get(item.record_type, 99),
                item.display_order,
                item.id,
            ),
        ):
            role = _COMMISSION_ROLE_LABELS.get(member.record_type, member.record_type)
            parts = [f"• {member.display_name} ({role})"]
            if member.role_text:
                parts.append(f"role: {member.role_text}")
            if member.note_text:
                parts.append(f"poznámka: {member.note_text}")
            lines.append("; ".join(parts))
        return lines

    def commission_text(self) -> str:
        lines = self.commission_lines()
        return "\n".join(lines) if lines else "Nejsou evidováni."

    def findings_lines(self) -> list[str]:
        findings = finding_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id)
        if not findings:
            return []

        lines: list[str] = []
        for index, finding in enumerate(
            sorted(findings, key=lambda item: (item.display_order, item.id)),
            start=1,
        ):
            parts = [f"{index}. {finding_type_label(finding.finding_type)}"]
            if finding.source_area_label:
                parts.append(f"oblast: {finding.source_area_label}")
            if finding.source_section_label:
                parts.append(f"sekce: {finding.source_section_label}")
            if finding.source_control_point_label:
                parts.append(f"kontrolní bod: {finding.source_control_point_label}")
            if finding.reference_label:
                parts.append(f"reference: {finding.reference_label}")
            if finding.description:
                parts.append(f"popis: {_text(finding.description)}")
            parts.append(f"stav: {finding_status_label(finding.status)}")
            if finding.recommended_action:
                parts.append(f"doporučení: {_text(finding.recommended_action)}")
            if finding.due_date:
                parts.append(f"termín: {_fmt_date(finding.due_date)}")
            if finding.responsible_person_name:
                parts.append(f"odpovědná osoba: {finding.responsible_person_name}")
            lines.append("; ".join(parts))
        return lines

    def findings_text(self) -> str:
        lines = self.findings_lines()
        return "\n".join(lines) if lines else "Nejsou evidována."

    def tasks_lines(self) -> list[str]:
        tasks = bozp_inspection_service.get_tasks_for_inspection(self.inspection_id)
        if not tasks:
            return []

        lines: list[str] = []
        for index, task in enumerate(tasks, start=1):
            parts = [f"{index}. {task.title or 'Úkol'}"]
            if task.responsible_person:
                parts.append(f"odpovídá: {task.responsible_person}")
            if task.due_date:
                parts.append(f"termín: {_fmt_date(task.due_date)}")
            parts.append(f"stav: {task.computed_status}")
            if task.note:
                parts.append(f"poznámka: {_text(task.note)}")
            lines.append("; ".join(parts))
        return lines

    def tasks_text(self) -> str:
        lines = self.tasks_lines()
        return "\n".join(lines) if lines else "Nejsou evidována."

    def statistics_text(self) -> str:
        stats = control_activity_statistics_service.compute(
            ENTITY_PROVERKY,
            self.inspection_id,
        )
        return stats.format_text()

    def summary_text(self) -> str:
        summary = bozp_inspection_service.get_conclusion_summary(self.inspection_id)
        return (
            f"{self.statistics_text()}\n\n"
            f"Otevřená zjištění: {summary['findings_open']}\n"
            f"Aktivní úkoly: {summary['tasks_active']}\n"
            f"Stav prověrky: {self.status_label()}"
        )

    def placeholder_values(self) -> dict[str, str]:
        return {
            "cislo_proverky": _text(self.inspection.number),
            "zamestnavatel_nazev": self.employer_name(),
            "pracoviste": _text(self.inspection.workplace_name),
            "rok": str(self.inspection.year or ""),
            "planovany_mesic": self.planned_month_label(),
            "typ_proverky": _text(self.inspection.inspection_type),
            "datum_proverky": _fmt_date(self.inspection.inspection_date),
            "datum_zahajeni": _fmt_date(self.inspection.started_at),
            "datum_ukonceni": _fmt_date(self.inspection.finished_at),
            "stav": self.status_label(),
            "komise_text": self.commission_text(),
            "zjisteni_text": self.findings_text(),
            "ukoly_text": self.tasks_text(),
            "statistika_text": self.statistics_text(),
            "souhrn_text": self.summary_text(),
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
        }


class BozpInspectionExportContextService:
    def build(self, inspection: BozpInspection) -> InspectionExportContext:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")
        return InspectionExportContext(inspection=inspection)

    def is_completed(self, inspection: BozpInspection) -> bool:
        return InspectionExportContext(inspection=inspection).is_completed()


bozp_inspection_export_context_service = BozpInspectionExportContextService()
