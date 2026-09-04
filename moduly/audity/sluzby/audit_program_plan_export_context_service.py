"""Read-only podklady pro ODT export plánu interních auditů."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from xml.sax.saxutils import escape as xml_escape

from core.export.odt_engine import OdtRichContent, OdtXmlFragment
from moduly.audity.sluzby.audit_knowledge_service import (
    AuditCatalogError,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_visit_formatting import (
    format_month_name,
    format_visit_term,
)

MISSING_VISIT_PROCESSES_WARNING = (
    "Některé plánované návštěvy nemají přiřazené auditované procesy."
)


def _display(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "none":
        return ""
    return text


def _header_value(value) -> str:
    return _display(value) or "—"


def _format_period(date_from: date | None, date_to: date | None) -> str:
    if date_from is None and date_to is None:
        return ""
    if date_from is None:
        return f"{date_to.day}. {date_to.month}. {date_to.year}"
    if date_to is None:
        return f"{date_from.day}. {date_from.month}. {date_from.year}"
    return (
        f"{date_from.day}. {date_from.month}. {date_from.year} – "
        f"{date_to.day}. {date_to.month}. {date_to.year}"
    )


def _format_created_at(value: datetime | date | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.day}. {value.month}. {value.year}"
    return _display(value)


def _cell_paragraph(text: str, *, align_right: bool = False) -> str:
    style_name = "PlanCellRight" if align_right else "Standard"
    return (
        f'<text:p text:style-name="{style_name}">'
        f"{xml_escape(_header_value(text))}"
        f"</text:p>"
    )


def _table_cell(text: str, *, style: str = "PlanCell", align_right: bool = False) -> str:
    return (
        '<table:table-cell office:value-type="string" '
        f'table:style-name="{style}">'
        f"{_cell_paragraph(text, align_right=align_right)}"
        "</table:table-cell>"
    )


def _header_cell(text: str) -> str:
    return (
        '<table:table-cell office:value-type="string" table:style-name="PlanHeaderCell">'
        f'<text:p text:style-name="PlanHeader">{xml_escape(text)}</text:p>'
        "</table:table-cell>"
    )


def _build_table(
    *,
    name: str,
    style: str,
    column_styles: tuple[str, ...],
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    right_align_last: bool = False,
) -> OdtXmlFragment:
    columns = "".join(
        f'<table:table-column table:style-name="{column_style}"/>'
        for column_style in column_styles
    )
    header_row = (
        "<table:table-header-rows><table:table-row table:style-name=\"PlanHeaderRow\">"
        + "".join(_header_cell(item) for item in headers)
        + "</table:table-row></table:table-header-rows>"
    )
    body_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for index, value in enumerate(row):
            align_right = right_align_last and index == len(row) - 1
            cells.append(_table_cell(value, align_right=align_right))
        body_rows.append(
            '<table:table-row table:style-name="PlanBodyRow">'
            + "".join(cells)
            + "</table:table-row>"
        )
    xml = (
        f'<table:table table:name="{xml_escape(name)}" table:style-name="{style}">'
        f"{columns}{header_row}{''.join(body_rows)}</table:table>"
    )
    return OdtXmlFragment(xml=xml)


@dataclass(frozen=True)
class AuditProgramPlanScheduleRow:
    visit_id: int
    year_label: str
    month_label: str
    workplace_name: str
    term_label: str
    has_processes: bool
    sort_key: tuple


@dataclass(frozen=True)
class AuditProgramPlanProcessRow:
    process_id: str
    process_name: str
    workplaces: tuple[str, ...]
    visit_count: int
    sort_key: tuple


@dataclass(frozen=True)
class AuditProgramPlanExportContext:
    program_number: str
    program_name: str
    period: str
    created_on: str
    schedule_rows: tuple[AuditProgramPlanScheduleRow, ...]
    process_rows: tuple[AuditProgramPlanProcessRow, ...]
    visits_without_processes: tuple[AuditProgramPlanScheduleRow, ...]

    def placeholder_values(self) -> dict[str, object]:
        warning: str | OdtRichContent
        if self.visits_without_processes:
            lines = [MISSING_VISIT_PROCESSES_WARNING, ""]
            for row in self.visits_without_processes:
                workplace = row.workplace_name or "—"
                lines.append(f"• {workplace} — {row.term_label}")
            warning = "\n".join(lines)
        else:
            warning = OdtRichContent(omit_when_empty=True)
        return {
            "program_cislo": _header_value(self.program_number),
            "program_nazev": _header_value(self.program_name),
            "obdobi_programu": _header_value(self.period),
            "datum_vytvoreni_planu": _header_value(self.created_on),
            "harmonogram_tabulka": self._schedule_table(),
            "souhrn_procesu_tabulka": self._process_table(),
            "chybejici_procesy_upozorneni": warning,
        }

    def _schedule_table(self) -> OdtXmlFragment:
        rows = [
            (row.year_label, row.month_label, row.workplace_name)
            for row in self.schedule_rows
        ]
        return _build_table(
            name="Harmonogram",
            style="HarmonogramTable",
            column_styles=("HarmonogramColA", "HarmonogramColB", "HarmonogramColC"),
            headers=("Rok", "Plánovaný měsíc", "Auditovaný provoz"),
            rows=rows,
        )

    def _process_table(self) -> OdtXmlFragment:
        rows = [
            (
                row.process_name,
                ", ".join(row.workplaces) if row.workplaces else "—",
                str(row.visit_count),
            )
            for row in self.process_rows
        ]
        return _build_table(
            name="SouhrnProcesu",
            style="ProcessTable",
            column_styles=("ProcessColA", "ProcessColB", "ProcessColC"),
            headers=(
                "Auditovaný proces",
                "Provozy zahrnuté v plánu",
                "Počet plánovaných ověření",
            ),
            rows=rows,
            right_align_last=True,
        )


class AuditProgramPlanExportContextService:
    def build(self, program_id: int) -> AuditProgramPlanExportContext:
        overview = audit_program_service.get_program_overview(program_id)
        if overview is None:
            raise ValueError("Auditní program nebyl nalezen.")

        program = overview.program
        workplace_names = {
            workplace.workplace_id: _display(workplace.workplace_name)
            for workplace in overview.workplaces
        }
        processes_by_visit: dict[int, list] = {}
        for item in overview.visit_processes:
            processes_by_visit.setdefault(int(item.visit_id), []).append(item)

        schedule_rows = [
            self._schedule_row(visit, workplace_names, processes_by_visit)
            for visit in overview.visits
        ]
        schedule_rows.sort(key=lambda row: row.sort_key)

        process_rows = self._process_rows(
            overview.visit_processes,
            schedule_by_id={row.visit_id: row for row in schedule_rows},
        )
        missing = tuple(row for row in schedule_rows if not row.has_processes)
        return AuditProgramPlanExportContext(
            program_number=_display(program.number),
            program_name=_display(program.name),
            period=_format_period(program.date_from, program.date_to),
            created_on=_format_created_at(program.created_at),
            schedule_rows=tuple(schedule_rows),
            process_rows=tuple(process_rows),
            visits_without_processes=missing,
        )

    @staticmethod
    def _schedule_row(visit, workplace_names: dict, processes_by_visit: dict):
        workplace = workplace_names.get(visit.workplace_id) or ""
        year = visit.planned_year
        month = visit.planned_month
        year_sort = int(year) if year else 9999
        month_sort = int(month) if month else 99
        return AuditProgramPlanScheduleRow(
            visit_id=int(visit.id),
            year_label=str(year) if year else "—",
            month_label=format_month_name(month),
            workplace_name=workplace or "—",
            term_label=format_visit_term(visit),
            has_processes=bool(processes_by_visit.get(int(visit.id))),
            sort_key=(year_sort, month_sort, workplace.casefold(), int(visit.id)),
        )

    @staticmethod
    def _process_rows(visit_processes, *, schedule_by_id: dict[int, AuditProgramPlanScheduleRow]):
        catalog_order: dict[str, int] = {}
        catalog_names: dict[str, str] = {}
        try:
            for process in audit_knowledge_service.get_processes(include_inactive=True):
                catalog_order[process.id] = int(process.poradi)
                catalog_names[process.id] = process.nazev
        except AuditCatalogError:
            pass

        grouped: dict[str, dict] = {}
        for item in visit_processes:
            process_id = str(item.process_id or "").strip() or f"id:{item.id}"
            bucket = grouped.setdefault(
                process_id,
                {
                    "names": set(),
                    "workplaces": set(),
                    "visit_ids": set(),
                },
            )
            name = _display(item.process_name) or catalog_names.get(process_id) or process_id
            if name:
                bucket["names"].add(name)
            visit_id = int(item.visit_id)
            bucket["visit_ids"].add(visit_id)
            schedule = schedule_by_id.get(visit_id)
            if schedule is not None and schedule.workplace_name and schedule.workplace_name != "—":
                bucket["workplaces"].add(schedule.workplace_name)

        rows: list[AuditProgramPlanProcessRow] = []
        for process_id, bucket in grouped.items():
            names = sorted(bucket["names"], key=str.casefold)
            process_name = names[0] if names else process_id
            workplaces = tuple(sorted(bucket["workplaces"], key=str.casefold))
            order = catalog_order.get(process_id, 10_000)
            rows.append(
                AuditProgramPlanProcessRow(
                    process_id=process_id,
                    process_name=process_name,
                    workplaces=workplaces,
                    visit_count=len(bucket["visit_ids"]),
                    sort_key=(order, process_name.casefold(), process_id),
                )
            )
        rows.sort(key=lambda row: row.sort_key)
        return rows


audit_program_plan_export_context_service = AuditProgramPlanExportContextService()
