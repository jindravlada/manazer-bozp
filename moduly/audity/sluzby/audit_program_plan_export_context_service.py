"""Read-only podklady pro ODT export plánu interních auditů."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from xml.sax.saxutils import escape as xml_escape

from core.export.odt_engine import OdtXmlFragment
from moduly.audity.sluzby.audit_knowledge_service import (
    AuditCatalogError,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_visit_formatting import format_month_name

VISIT_PROCESSES_NOT_ASSIGNED = "Procesy nejsou přiřazeny."


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
    if date_to is None:
        return f"{date_from.day}. {date_from.month}. {date_from.year}"
    if date_from is None:
        return f"{date_to.day}. {date_to.month}. {date_to.year}"
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


def _table_cell(
    value: str | tuple[str, ...],
    *,
    style: str = "PlanCell",
    align_right: bool = False,
) -> str:
    lines = value if isinstance(value, tuple) else (value,)
    if not lines:
        lines = ("—",)
    paragraphs = "".join(
        _cell_paragraph(line, align_right=align_right) for line in lines
    )
    return (
        '<table:table-cell office:value-type="string" '
        f'table:style-name="{style}">'
        f"{paragraphs}"
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
    rows: list[tuple[str | tuple[str, ...], ...]],
) -> OdtXmlFragment:
    columns = "".join(
        f'<table:table-column table:style-name="{column_style}"/>'
        for column_style in column_styles
    )
    header_row = (
        '<table:table-header-rows><table:table-row table:style-name="PlanHeaderRow">'
        + "".join(_header_cell(item) for item in headers)
        + "</table:table-row></table:table-header-rows>"
    )
    body_rows: list[str] = []
    for row in rows:
        cells = "".join(_table_cell(value) for value in row)
        body_rows.append(
            '<table:table-row table:style-name="PlanBodyRow">'
            + cells
            + "</table:table-row>"
        )
    xml = (
        f'<table:table table:name="{xml_escape(name)}" table:style-name="{style}">'
        f"{columns}{header_row}{''.join(body_rows)}</table:table>"
    )
    return OdtXmlFragment(xml=xml)


def _catalog_process_maps() -> tuple[dict[str, int], dict[str, str]]:
    catalog_order: dict[str, int] = {}
    catalog_names: dict[str, str] = {}
    try:
        for process in audit_knowledge_service.get_processes(include_inactive=True):
            catalog_order[process.id] = int(process.poradi)
            catalog_names[process.id] = process.nazev
    except AuditCatalogError:
        pass
    return catalog_order, catalog_names


def _sorted_process_names(
    items,
    *,
    catalog_order: dict[str, int],
    catalog_names: dict[str, str],
) -> tuple[str, ...]:
    ranked: list[tuple[int, str, str, str]] = []
    for item in items:
        process_id = str(item.process_id or "").strip() or f"id:{item.id}"
        name = _display(item.process_name) or catalog_names.get(process_id) or process_id
        order = catalog_order.get(process_id, 10_000)
        ranked.append((order, name.casefold(), process_id, name))
    ranked.sort()
    names: list[str] = []
    seen: set[str] = set()
    for _order, _key, process_id, name in ranked:
        if process_id in seen:
            continue
        seen.add(process_id)
        names.append(name)
    return tuple(names)


@dataclass(frozen=True)
class AuditProgramPlanScheduleRow:
    visit_id: int
    year_label: str
    month_label: str
    workplace_name: str
    process_names: tuple[str, ...]
    sort_key: tuple

    @property
    def has_processes(self) -> bool:
        return bool(self.process_names)

    @property
    def process_cell_lines(self) -> tuple[str, ...]:
        if self.process_names:
            return self.process_names
        return (VISIT_PROCESSES_NOT_ASSIGNED,)


@dataclass(frozen=True)
class AuditProgramPlanExportContext:
    program_number: str
    program_name: str
    period: str
    created_on: str
    schedule_rows: tuple[AuditProgramPlanScheduleRow, ...]

    def placeholder_values(self) -> dict[str, object]:
        return {
            "program_cislo": _header_value(self.program_number),
            "program_nazev": _header_value(self.program_name),
            "obdobi_programu": _header_value(self.period),
            "datum_vytvoreni_planu": _header_value(self.created_on),
            "harmonogram_tabulka": self._schedule_table(),
        }

    def _schedule_table(self) -> OdtXmlFragment:
        rows = [
            (
                row.year_label,
                row.month_label,
                row.workplace_name,
                row.process_cell_lines,
            )
            for row in self.schedule_rows
        ]
        return _build_table(
            name="Harmonogram",
            style="HarmonogramTable",
            column_styles=(
                "HarmonogramColA",
                "HarmonogramColB",
                "HarmonogramColC",
                "HarmonogramColD",
            ),
            headers=("Rok", "Plánovaný měsíc", "Auditovaný provoz", "Auditované procesy"),
            rows=rows,
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

        catalog_order, catalog_names = _catalog_process_maps()
        schedule_rows = [
            self._schedule_row(
                visit,
                workplace_names,
                processes_by_visit,
                catalog_order=catalog_order,
                catalog_names=catalog_names,
            )
            for visit in overview.visits
        ]
        schedule_rows.sort(key=lambda row: row.sort_key)
        return AuditProgramPlanExportContext(
            program_number=_display(program.number),
            program_name=_display(program.name),
            period=_format_period(program.date_from, program.date_to),
            created_on=_format_created_at(program.created_at),
            schedule_rows=tuple(schedule_rows),
        )

    @staticmethod
    def _schedule_row(
        visit,
        workplace_names: dict,
        processes_by_visit: dict,
        *,
        catalog_order: dict[str, int],
        catalog_names: dict[str, str],
    ):
        workplace = workplace_names.get(visit.workplace_id) or ""
        year = visit.planned_year
        month = visit.planned_month
        year_sort = int(year) if year else 9999
        month_sort = int(month) if month else 99
        process_names = _sorted_process_names(
            processes_by_visit.get(int(visit.id), []),
            catalog_order=catalog_order,
            catalog_names=catalog_names,
        )
        return AuditProgramPlanScheduleRow(
            visit_id=int(visit.id),
            year_label=str(year) if year else "—",
            month_label=format_month_name(month),
            workplace_name=workplace or "—",
            process_names=process_names,
            sort_key=(year_sort, month_sort, workplace.casefold(), int(visit.id)),
        )


audit_program_plan_export_context_service = AuditProgramPlanExportContextService()
