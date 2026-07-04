from dataclasses import dataclass
from datetime import date, datetime

from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_PROVERKY,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.proverky.constants import (
    COMMISSION_RECORD_LEADER,
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


def _format_labeled_block(
    index: int,
    title: str,
    fields: list[tuple[str, str]],
) -> str:
    lines = [f"{index}. {title}"]
    for label, value in fields:
        text = _text(value)
        if text:
            lines.append(f"   {label}: {text}")
    return "\n".join(lines)


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(blocks)


@dataclass(frozen=True)
class InspectionExportContext:
    """Sjednocený kontext exportu zprávy z prověrky BOZP."""

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

    def program_label(self) -> str:
        year = self.inspection.year
        if year:
            return f"Prověrky BOZP {year}"
        return "Prověrky BOZP"

    def commission_member_name(self, record_type: str) -> str:
        for member in bozp_inspection_commission_service.get_for_inspection(self.inspection_id):
            if member.record_type == record_type:
                return _text(member.display_name)
        return "—"

    def leader_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_LEADER)

    def workplace_representative_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_WORKPLACE)

    def controlled_operation_label(self) -> str:
        return self.employer_name() or "—"

    def controlled_workplace_label(self) -> str:
        return _text(self.inspection.workplace_name) or "—"

    def controlled_areas_lines(self) -> list[str]:
        seen: set[str] = set()
        areas: list[str] = []
        for result in control_result_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id):
            label = _text(result.source_area_label)
            if not label or label in seen:
                continue
            seen.add(label)
            areas.append(label)
        return sorted(areas, key=str.casefold)

    def controlled_areas_text(self) -> str:
        lines = self.controlled_areas_lines()
        if not lines:
            return "Nejsou evidovány."
        return "\n".join(f"• {line}" for line in lines)

    def _activity_statistics(self):
        return control_activity_statistics_service.compute(ENTITY_PROVERKY, self.inspection_id)

    def overall_assessment_text(self) -> str:
        stats = self._activity_statistics()
        if stats.ratings_nevyhovuje:
            first_sentence = (
                "Prověrka BOZP prokázala nedostatky vyžadující nápravu "
                "na kontrolovaném pracovišti."
            )
        elif stats.ratings_vyhovuje_s_doporucenim:
            first_sentence = (
                "Prověrka BOZP potvrdila obecně vyhovující stav s doporučeními "
                "ke zlepšení."
            )
        else:
            first_sentence = (
                "Prověrka BOZP neprokázala závažné nedostatky "
                "na kontrolovaném pracovišti."
            )

        detail_parts: list[str] = []
        if stats.ratings_nevyhovuje == 1:
            detail_parts.append("1 neshoda")
        elif stats.ratings_nevyhovuje > 1:
            detail_parts.append(f"{stats.ratings_nevyhovuje} neshody")
        if stats.ratings_vyhovuje_s_doporucenim == 1:
            detail_parts.append("1 příležitost ke zlepšení")
        elif stats.ratings_vyhovuje_s_doporucenim > 1:
            detail_parts.append(
                f"{stats.ratings_vyhovuje_s_doporucenim} příležitosti ke zlepšení"
            )

        if detail_parts:
            if len(detail_parts) == 2:
                second_sentence = (
                    f"Během prověrky byla zjištěna {detail_parts[0]} a {detail_parts[1]}. "
                )
            else:
                second_sentence = f"Během prověrky byla zjištěna {detail_parts[0]}. "
        else:
            second_sentence = "Během prověrky nebyla zjištěna významná zjištění. "

        if stats.ratings_nevyhovuje >= 3:
            second_sentence += "Bylo prokázáno systémové selhání v některých oblastech."
        else:
            second_sentence += "Prověrka neprokázala systémové selhání."
        return f"{first_sentence}\n{second_sentence}"

    def results_overview_text(self) -> str:
        stats = self._activity_statistics()
        summary = bozp_inspection_service.get_conclusion_summary(self.inspection_id)
        return "\n".join(
            [
                f"Kontrolovaných oblastí: {stats.areas_checked}",
                f"Kontrolních bodů: {stats.control_points_checked}",
                f"Vyhovuje: {stats.ratings_vyhovuje}",
                f"Vyhovuje s doporučením: {stats.ratings_vyhovuje_s_doporucenim}",
                f"Nevyhovuje: {stats.ratings_nevyhovuje}",
                f"Zjištění: {stats.findings_total}",
                f"Otevřené úkoly: {summary['tasks_active']}",
            ]
        )

    def strengths_text(self) -> str:
        raw = _text(getattr(self.inspection, "silne_stranky", ""))
        if not raw:
            return "—"
        lines: list[str] = []
        for line in raw.split("\n"):
            text = line.strip()
            if not text:
                continue
            if text.startswith("✔"):
                lines.append(text)
            else:
                lines.append(f"✔ {text}")
        return "\n".join(lines) if lines else "—"

    def attention_areas_text(self) -> str:
        results = control_result_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id)
        lines: list[str] = []
        for row in sorted(
            results,
            key=lambda item: (
                0 if item.result == CONTROL_RESULT_NEVYHOVUJE else 1,
                item.source_area_label,
                item.source_section_label,
                item.source_control_point_label,
                item.id,
            ),
        ):
            label = self._attention_area_label(row)
            if row.result == CONTROL_RESULT_NEVYHOVUJE:
                lines.append(f"🔴 {label}")
            elif row.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM:
                lines.append(f"🟡 {label}")
        return "\n".join(lines) if lines else "—"

    @staticmethod
    def _attention_area_label(row) -> str:
        for attr in ("source_control_point_label", "note", "source_section_label"):
            value = _text(getattr(row, attr, ""))
            if value:
                return value
        return "—"

    def leader_recommendation_text(self) -> str:
        raw = _text(getattr(self.inspection, "doporuceni_vedouciho", ""))
        return raw or "—"

    def inspection_scope_text(self) -> str:
        return (
            "Prověrka byla provedena v souladu s plánem kontrol BOZP.\n"
            "Kontrolované oblasti jsou uvedeny v příloze této zprávy."
        )

    def findings_lines(self) -> list[str]:
        findings = finding_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id)
        if not findings:
            return []

        lines: list[str] = []
        for index, finding in enumerate(
            sorted(findings, key=lambda item: (item.display_order, item.id)),
            start=1,
        ):
            lines.append(
                _format_labeled_block(
                    index,
                    finding_type_label(finding.finding_type),
                    [
                        ("Oblast", finding.source_area_label),
                        ("Sekce", finding.source_section_label),
                        ("Kontrolní bod", finding.source_control_point_label),
                        ("Reference", finding.reference_label),
                        ("Popis", finding.description),
                        ("Doporučení", finding.recommended_action),
                        ("Termín", _fmt_date(finding.due_date)),
                        ("Odpovědná osoba", finding.responsible_person_name),
                        ("Stav", finding_status_label(finding.status)),
                    ],
                )
            )
        return lines

    def findings_text(self) -> str:
        lines = self.findings_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def findings_detail_text(self) -> str:
        return self.findings_text()

    def tasks_lines(self) -> list[str]:
        tasks = bozp_inspection_service.get_tasks_for_inspection(self.inspection_id)
        if not tasks:
            return []

        lines: list[str] = []
        for index, task in enumerate(tasks, start=1):
            lines.append(
                _format_labeled_block(
                    index,
                    task.title or "Úkol",
                    [
                        ("Odpovídá", task.responsible_person),
                        ("Termín", _fmt_date(task.due_date)),
                        ("Stav", task.computed_status),
                        ("Splněno", _fmt_date(task.completed_date)),
                        ("Poznámka", task.note),
                    ],
                )
            )
        return lines

    def tasks_text(self) -> str:
        lines = self.tasks_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována."

    def accepted_measures_text(self) -> str:
        return self.tasks_text()

    def statistics_text(self) -> str:
        return self.results_overview_text()

    def summary_text(self) -> str:
        stats = self._activity_statistics()
        summary = bozp_inspection_service.get_conclusion_summary(self.inspection_id)
        return "\n".join(
            [
                self.results_overview_text(),
                "",
                f"Otevřená zjištění: {summary['findings_open']}",
                f"Aktivní úkoly: {summary['tasks_active']}",
                f"Stav prověrky: {self.status_label()}",
                f"Počet kontrolovaných oblastí: {stats.areas_checked}",
            ]
        )

    def placeholder_values(self) -> dict[str, str]:
        results_overview = self.results_overview_text()
        findings_detail = self.findings_detail_text()
        accepted_measures = self.accepted_measures_text()
        summary = self.summary_text()

        return {
            "cislo_proverky": _text(self.inspection.number),
            "zamestnavatel_nazev": self.employer_name(),
            "pracoviste": self.controlled_workplace_label(),
            "provoz": self.controlled_operation_label(),
            "program_proverek": self.program_label(),
            "rok": str(self.inspection.year or ""),
            "planovany_mesic": self.planned_month_label(),
            "typ_proverky": _text(self.inspection.inspection_type),
            "datum_proverky": _fmt_date(self.inspection.inspection_date),
            "datum_zahajeni": _fmt_date(self.inspection.started_at),
            "datum_ukonceni": _fmt_date(self.inspection.finished_at),
            "stav": self.status_label(),
            "komise_text": self._legacy_commission_text(),
            "kontrolovany_provoz": self.controlled_operation_label(),
            "kontrolovane_pracoviste": self.controlled_workplace_label(),
            "vedouci_proverky": self.leader_name(),
            "zastupce_pracoviste": self.workplace_representative_name(),
            "celkove_hodnoceni_text": self.overall_assessment_text(),
            "prehled_vysledku_text": results_overview,
            "silne_stranky_text": self.strengths_text(),
            "oblasti_pozornosti_text": self.attention_areas_text(),
            "doporuceni_vedouciho": self.leader_recommendation_text(),
            "doporuceni_proverky": self.leader_recommendation_text(),
            "rozsah_proverky_text": self.inspection_scope_text(),
            "detail_zjisteni_text": findings_detail,
            "prijata_opatreni_text": accepted_measures,
            "priloha_oblasti_text": self.controlled_areas_text(),
            "zjisteni_text": findings_detail,
            "ukoly_text": accepted_measures,
            "statistika_text": results_overview,
            "souhrn_text": summary,
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
        }

    def _legacy_commission_text(self) -> str:
        members = bozp_inspection_commission_service.get_for_inspection(self.inspection_id)
        if not members:
            return "Nejsou evidováni."
        lines = [f"• {member.display_name}" for member in members]
        return "\n".join(lines)


class BozpInspectionExportContextService:
    def build(self, inspection: BozpInspection) -> InspectionExportContext:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")
        return InspectionExportContext(inspection=inspection)

    def is_completed(self, inspection: BozpInspection) -> bool:
        return InspectionExportContext(inspection=inspection).is_completed()


bozp_inspection_export_context_service = BozpInspectionExportContextService()
