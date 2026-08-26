from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from core.export.commission_display import (
    COMMISSION_LABEL_LEADER_INSPECTION,
    COMMISSION_LABEL_UNION,
    COMMISSION_LABEL_WORKPLACE,
    build_commission_sections,
    commission_sections_text,
)
from core.export.control_point_appendix import (
    DEFAULT_RESULT_EMOJI,
    ControlPointAppendixItem,
    build_areas_appendix,
    build_detailed_control_points_appendix,
    section_summary_paragraphs,
)
from core.export.odt_engine import OdtParagraph, OdtRichContent
from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
    ENTITY_PROVERKY,
)
from core.shared.control_result_display import (
    control_result_label,
    protocol_evaluation_results,
)
from core.shared.finding_display import finding_status_label, finding_type_label
from core.shared.section_summary import uses_section_summary_notes_mode
from core.shared.sluzby.control_activity_statistics_service import (
    control_activity_statistics_service,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.proverky.constants import (
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
    INSPECTION_STRENGTHS_EXPORT_SECTION,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.proverky.modely.bozp_inspection import BozpInspection
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.inspection_section_summary_service import (
    inspection_section_summary_service,
)


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


_STRENGTHS_EMPTY_PLACEHOLDER = "—"


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


def _zavady_phrase(count: int) -> str:
    if count == 1:
        return "1 závada"
    if 2 <= count <= 4:
        return f"{count} závady"
    return f"{count} závad"


_OVERVIEW_RESULT_TITLES = {
    CONTROL_RESULT_NEVYHOVUJE: "Závada",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "Doporučení",
}


@dataclass(frozen=True)
class InspectionExportDocumentConfig:
    """Konfigurace výstupního dokumentu z prověrky (protokol vs. podrobná zpráva)."""

    include_signatures: bool = True
    detailed_report: bool = False


PROTOCOL_DOCUMENT_CONFIG = InspectionExportDocumentConfig(
    include_signatures=True,
    detailed_report=False,
)

DETAILED_REPORT_DOCUMENT_CONFIG = InspectionExportDocumentConfig(
    include_signatures=False,
    detailed_report=True,
)


@dataclass(frozen=True)
class InspectionExportContext:
    """Sjednocený kontext exportu protokolu / podrobné zprávy z prověrky BOZP."""

    inspection: BozpInspection
    config: InspectionExportDocumentConfig = PROTOCOL_DOCUMENT_CONFIG

    @property
    def inspection_id(self) -> int:
        return self.inspection.id

    def _uses_section_summary_notes(self) -> bool:
        return uses_section_summary_notes_mode(
            getattr(self.inspection, "notes_mode", None)
        )

    def _section_summaries_map(self) -> dict[tuple[str, str], str]:
        cached = getattr(self, "_section_summaries_cache", None)
        if cached is not None:
            return cached
        mapping = inspection_section_summary_service.map_for_inspection(self.inspection_id)
        object.__setattr__(self, "_section_summaries_cache", mapping)
        return mapping

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

    def inspection_title_label(self) -> str:
        title = _text(self.inspection.title)
        if title:
            return title
        typ = _text(self.inspection.inspection_type)
        workplace = self.controlled_operation_label()
        if typ and workplace and workplace != "—":
            return f"{typ} – {workplace}"
        return typ or workplace or "Prověrka BOZP"

    def commission_member_name(self, record_type: str) -> str:
        for member in bozp_inspection_commission_service.get_for_inspection(self.inspection_id):
            if member.record_type == record_type:
                return _text(member.display_name)
        return "—"

    def leader_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_LEADER)

    def workplace_representative_name(self) -> str:
        return self.commission_member_name(COMMISSION_RECORD_WORKPLACE)

    def union_representative_name(self) -> str:
        name = self.commission_member_name(COMMISSION_RECORD_UNION)
        return "" if name == "—" else name

    def union_signature_block_text(self) -> str:
        name = self.union_representative_name()
        if not name:
            return ""
        return "\n".join(
            [
                COMMISSION_LABEL_UNION,
                name,
                "........................................",
                "podpis",
            ]
        )

    def signatures_text(self) -> str:
        blocks = [
            "\n".join(
                [
                    COMMISSION_LABEL_LEADER_INSPECTION,
                    self.leader_name(),
                    "........................................",
                    "podpis",
                ]
            ),
            "\n".join(
                [
                    COMMISSION_LABEL_WORKPLACE,
                    self.workplace_representative_name(),
                    "........................................",
                    "podpis",
                ]
            ),
        ]
        union_block = self.union_signature_block_text()
        if union_block:
            blocks.append(union_block)
        return "\n\n".join(blocks)

    def controlled_operation_label(self) -> str:
        """Kontrolovaný provoz = hodnota kontrolovaného pracoviště."""
        return _text(self.inspection.workplace_name) or "—"

    def controlled_workplace_label(self) -> str:
        return self.controlled_operation_label()

    def inspection_start_date_text(self) -> str:
        return _fmt_date(self.inspection.started_at)

    def inspection_end_date_text(self) -> str:
        if not self.inspection.finished_at:
            return "Dosud neukončena"
        return _fmt_date(self.inspection.finished_at)

    def _commission_members(self):
        return bozp_inspection_commission_service.get_for_inspection(self.inspection_id)

    def _commission_names_for_type(self, record_type: str) -> list[str]:
        names: list[str] = []
        for member in sorted(
            self._commission_members(),
            key=lambda item: (item.display_order, item.id),
        ):
            if member.record_type != record_type:
                continue
            name = _text(member.display_name)
            if name:
                names.append(name)
        return names

    def commission_sections(self):
        """Sekce komise ve stejném pořadí a formátu jako u auditu (bez prázdných)."""
        return build_commission_sections(
            leader_label=COMMISSION_LABEL_LEADER_INSPECTION,
            leader_names=self._commission_names_for_type(COMMISSION_RECORD_LEADER),
            workplace_names=self._commission_names_for_type(
                COMMISSION_RECORD_WORKPLACE
            ),
            union_names=self._commission_names_for_type(COMMISSION_RECORD_UNION),
            member_names=self._commission_names_for_type(COMMISSION_RECORD_MEMBER),
            invited_names=self._commission_names_for_type(COMMISSION_RECORD_INVITED),
        )

    def commission_lines(self) -> list[str]:
        """Kompletní složení komise – bez prázdných sekcí."""
        return [section.as_text() for section in self.commission_sections()]

    def commission_text(self) -> str:
        return commission_sections_text(self.commission_sections())

    def members_text(self) -> str:
        names = self._commission_names_for_type(COMMISSION_RECORD_MEMBER)
        return "\n".join(names)

    def invited_text(self) -> str:
        names = self._commission_names_for_type(COMMISSION_RECORD_INVITED)
        return "\n".join(names)

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

    def appendix_areas_text(self) -> OdtRichContent:
        """Příloha A – Kontrolované oblasti (netučné odrážky jako u protokolu auditu)."""
        return build_areas_appendix(self.controlled_areas_lines())

    def _control_point_results(self):
        return control_result_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id)

    def appendix_control_points_text(self) -> OdtRichContent:
        """Příloha B – protokol: jen kontrolní otázky; podrobná zpráva: i komentáře a foto."""
        if self.config.detailed_report:
            return self.detailed_appendix_control_points()
        return self.summary_appendix_control_points()

    def summary_appendix_control_points(self) -> OdtRichContent:
        """Příloha B protokolu – oblasti a kontrolní otázky s výsledkem, bez komentářů a fotek."""
        results = self._control_point_results()
        if not results:
            return OdtRichContent(paragraphs=[OdtParagraph.text("Nejsou evidovány.")])

        new_mode = self._uses_section_summary_notes()
        summaries = self._section_summaries_map() if new_mode else {}
        grouped: dict[object, list[str]] = {}
        headings: dict[object, str] = {}
        group_summaries: dict[object, str] = {}
        area_order: list[object] = []
        for row in sorted(
            results,
            key=lambda item: (
                item.source_area_label or "",
                item.source_section_label or "",
                item.source_control_point_label or "",
                item.id,
            ),
        ):
            control_point = _text(row.source_control_point_label)
            area = _text(row.source_area_label) or _text(row.source_section_label)
            if not control_point or not area:
                continue
            area_id = str(getattr(row, "source_area_id", "") or "").strip()
            section_id = str(getattr(row, "source_section_id", "") or "").strip()
            section = _text(row.source_section_label)
            if new_mode and area_id and section_id:
                group_id: object = (area_id, section_id)
                if area and section and area != section:
                    heading = f"{area} — {section}"
                else:
                    heading = section or area
            else:
                group_id = area
                heading = area
            emoji = DEFAULT_RESULT_EMOJI.get(row.result, "○")
            if group_id not in grouped:
                grouped[group_id] = []
                headings[group_id] = heading
                area_order.append(group_id)
                if new_mode and area_id and section_id:
                    group_summaries[group_id] = summaries.get((area_id, section_id), "")
            grouped[group_id].append(f"{emoji} {control_point}")

        paragraphs: list[OdtParagraph] = []
        for index, group_id in enumerate(area_order):
            lines = grouped.get(group_id) or []
            if not lines:
                continue
            if index > 0:
                paragraphs.append(OdtParagraph.blank_line())
            paragraphs.append(OdtParagraph.text(headings[group_id], style="AuditCriterion"))
            paragraphs.extend(section_summary_paragraphs(group_summaries.get(group_id, "")))
            for line in lines:
                paragraphs.append(OdtParagraph.text(line))
        if not paragraphs:
            return OdtRichContent(paragraphs=[OdtParagraph.text("Nejsou evidovány.")])
        return OdtRichContent(paragraphs=paragraphs)

    def detailed_appendix_control_points(self) -> OdtRichContent:
        """Příloha B podrobné zprávy – kontrolní body s komentáři a fotografiemi."""
        results = self._control_point_results()
        new_mode = self._uses_section_summary_notes()
        summaries = self._section_summaries_map() if new_mode else {}
        items: list[ControlPointAppendixItem] = []
        for row in sorted(
            results,
            key=lambda item: (
                item.source_area_label or "",
                item.source_section_label or "",
                item.source_control_point_label or "",
                item.id,
            ),
        ):
            control_point = _text(row.source_control_point_label)
            area = _text(row.source_area_label) or _text(row.source_section_label)
            if not control_point or not area:
                continue
            photo_path = control_result_service.resolve_photo_path(row)
            area_id = str(getattr(row, "source_area_id", "") or "").strip()
            section_id = str(getattr(row, "source_section_id", "") or "").strip()
            section = _text(row.source_section_label)
            if new_mode and area_id and section_id:
                section_key: tuple[str, str] | None = (area_id, section_id)
                if area and section and area != section:
                    heading = f"{area} — {section}"
                else:
                    heading = section or area
            else:
                section_key = None
                heading = area
            items.append(
                ControlPointAppendixItem(
                    area_label=heading,
                    control_point_label=control_point,
                    result=row.result,
                    note="" if new_mode else _text(getattr(row, "note", "")),
                    photo_path=photo_path if photo_path and photo_path.is_file() else None,
                    section_key=section_key,
                    section_summary=(
                        summaries.get(section_key, "") if section_key else ""
                    ),
                )
            )
        return build_detailed_control_points_appendix(
            items,
            note_label="Komentář:",
            include_recommendation=False,
            include_question_notes=not new_mode,
            empty_message="Nejsou evidovány.",
        )

    def findings_overview_lines(self) -> list[str]:
        """Souhrn závad a doporučení pro podrobnou zprávu."""
        included = protocol_evaluation_results()
        lines: list[str] = []
        for index, row in enumerate(
            sorted(
                (
                    item
                    for item in self._control_point_results()
                    if item.result in included
                ),
                key=lambda item: (
                    0 if item.result == CONTROL_RESULT_NEVYHOVUJE else 1,
                    item.source_area_label or "",
                    item.source_control_point_label or "",
                    item.id,
                ),
            ),
            start=1,
        ):
            title = _OVERVIEW_RESULT_TITLES.get(
                row.result,
                control_result_label(row.result),
            )
            fields = [
                ("Oblast", row.source_area_label),
                ("Kontrolní bod", row.source_control_point_label),
                ("Výsledek", control_result_label(row.result)),
            ]
            if not self._uses_section_summary_notes():
                fields.append(("Komentář", row.note))
            lines.append(
                _format_labeled_block(
                    index,
                    title,
                    fields,
                )
            )
        return lines

    def findings_overview_text(self) -> str:
        lines = self.findings_overview_lines()
        return _join_blocks(lines) if lines else "Nejsou evidována významná zjištění."

    def significant_findings_text(self) -> str:
        return self.findings_overview_text()

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
        if stats.ratings_nevyhovuje:
            detail_parts.append(_zavady_phrase(stats.ratings_nevyhovuje))
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
        """Odrážky silných stránek bez nadpisu; prázdné → prázdný řetězec."""
        lines = self._strength_lines()
        return "\n".join(lines) if lines else ""

    def _strength_items(self) -> list:
        raw = getattr(self.inspection, "silne_stranky", None)
        if raw is None:
            return []
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return str(raw).replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def _strength_lines(self) -> list[str]:
        lines: list[str] = []
        for item in self._strength_items():
            text = str(item or "").strip()
            if not text or text == _STRENGTHS_EMPTY_PLACEHOLDER:
                continue
            if text.startswith("✔"):
                lines.append(text)
            else:
                lines.append(f"✔ {text}")
        return lines

    def strengths_section_text(self) -> OdtRichContent:
        """Sekce Silné stránky — nadpis jen při alespoň jedné vyplněné stránce."""
        lines = self._strength_lines()
        if not lines:
            return OdtRichContent(paragraphs=[], omit_when_empty=True)
        paragraphs: list[OdtParagraph] = [
            OdtParagraph.text(INSPECTION_STRENGTHS_EXPORT_SECTION, style="H"),
        ]
        for line in lines:
            paragraphs.append(OdtParagraph.text(line))
        return OdtRichContent(paragraphs=paragraphs)

    def attention_areas_text(self) -> str:
        results = self._control_point_results()
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
            "Kontrolované oblasti jsou uvedeny v příloze A této zprávy.\n"
            "Výsledky jednotlivých kontrolních bodů jsou uvedeny v příloze B."
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

    def placeholder_values(self) -> dict[str, Any]:
        results_overview = self.results_overview_text()
        findings_detail = self.findings_detail_text()
        accepted_measures = self.accepted_measures_text()
        summary = self.summary_text()
        commission = self.commission_text()
        findings_overview = self.findings_overview_text()
        signatures = ""
        union_signature = ""
        if self.config.include_signatures:
            signatures = self.signatures_text()
            union_signature = self.union_signature_block_text()

        return {
            "cislo_proverky": _text(self.inspection.number),
            "nazev_proverky": self.inspection_title_label(),
            "zamestnavatel_nazev": self.employer_name(),
            "pracoviste": self.controlled_operation_label(),
            "provoz": self.controlled_operation_label(),
            "program_proverek": self.program_label(),
            "rok": str(self.inspection.year or ""),
            "planovany_mesic": self.planned_month_label(),
            "typ_proverky": _text(self.inspection.inspection_type),
            "datum_proverky": self.inspection_start_date_text(),
            "datum_zahajeni": self.inspection_start_date_text(),
            "datum_ukonceni": self.inspection_end_date_text(),
            "datum_zahajeni_proverky": self.inspection_start_date_text(),
            "datum_ukonceni_proverky": self.inspection_end_date_text(),
            "stav": self.status_label(),
            "komise_text": commission,
            "kontrolovany_provoz": self.controlled_operation_label(),
            "kontrolovane_pracoviste": self.controlled_operation_label(),
            "vedouci_proverky": self.leader_name(),
            "zastupce_pracoviste": self.workplace_representative_name(),
            "zastupce_provozu": self.workplace_representative_name(),
            "zastupce_odboru": self.union_representative_name(),
            "zastupce_odborove_organizace": self.union_representative_name(),
            # Podpisy: samostatný klíč – prázdný = podpisový řádek odborů pryč.
            "podpis_zastupce_odborove_organizace": self.union_representative_name(),
            "clenove_komise_text": self.members_text(),
            "prizvane_osoby_text": self.invited_text(),
            "podpis_odboru_blok": union_signature,
            "podpisy_text": signatures,
            "celkove_hodnoceni_text": self.overall_assessment_text(),
            "prehled_vysledku_text": results_overview,
            "prehled_zjisteni_text": findings_overview,
            "vyznamna_zjisteni_text": findings_overview,
            "silne_stranky_text": self.strengths_section_text(),
            "oblasti_pozornosti_text": self.attention_areas_text(),
            "doporuceni_vedouciho": self.leader_recommendation_text(),
            "doporuceni_proverky": self.leader_recommendation_text(),
            "rozsah_proverky_text": self.inspection_scope_text(),
            "detail_zjisteni_text": findings_detail,
            "prijata_opatreni_text": accepted_measures,
            "priloha_oblasti_text": self.appendix_areas_text(),
            "priloha_kontrolni_body_text": self.appendix_control_points_text(),
            "zjisteni_text": findings_detail,
            "ukoly_text": accepted_measures,
            "statistika_text": results_overview,
            "souhrn_text": summary,
            "datum_vygenerovani": datetime.now().strftime("%d.%m.%Y"),
        }


class BozpInspectionExportContextService:
    def build(
        self,
        inspection: BozpInspection,
        config: InspectionExportDocumentConfig | None = None,
    ) -> InspectionExportContext:
        if inspection is None or not getattr(inspection, "id", None):
            raise ValueError("Není vybraná uložená prověrka.")
        return InspectionExportContext(
            inspection=inspection,
            config=config or PROTOCOL_DOCUMENT_CONFIG,
        )

    def is_completed(self, inspection: BozpInspection) -> bool:
        return InspectionExportContext(inspection=inspection).is_completed()


bozp_inspection_export_context_service = BozpInspectionExportContextService()
