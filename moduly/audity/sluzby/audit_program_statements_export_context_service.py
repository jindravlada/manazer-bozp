"""Read-only podklady pro tisk auditních tvrzení vybrané návštěvy."""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape

from core.database.session import get_session
from core.export.odt_engine import OdtXmlFragment
from moduly.audity.constants import (
    AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY,
    AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_MARKS,
    AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_N,
    AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_NP,
    AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_V,
    AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_VD,
    AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT,
    AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN,
    EXTRAORDINARY_SNAPSHOT_ORDER_BASE,
    PROCESS_TERM_CRITERION,
    PROCESS_TERM_PROCESS,
    PROCESS_TERM_QUESTION,
)
from moduly.audity.sluzby.audit_extraordinary_assignment_service import (
    audit_extraordinary_assignment_service,
)
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    format_verification_type_label,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_visit_formatting import format_month_name
from moduly.audity.sluzby.audit_question_snapshot_service import (
    AuditQuestionSnapshotDraft,
    audit_question_snapshot_service,
)
from moduly.audity.sluzby.audit_question_source_service import (
    SnapshotAssertionView,
    audit_question_source_service,
    build_knowledge_tree_from_snapshot_views,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.system_audit_workplace_service import (
    system_audit_workplace_service,
)


class AuditProgramStatementsEmptyError(ValueError):
    """Návštěva nemá použitelná tvrzení — dokument se nevytvoří."""


def _display(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "none":
        return ""
    return text


def _header_value(value) -> str:
    return _display(value) or "—"


def _program_label(number: str, name: str) -> str:
    number_text = _display(number)
    name_text = _display(name)
    if number_text and name_text:
        return f"{number_text} – {name_text}"
    return number_text or name_text


def _planned_period(year: int | None, month: int | None) -> str:
    year_text = str(year) if year else ""
    month_text = format_month_name(month)
    if year_text and month_text:
        return f"{year_text} · {month_text}"
    return year_text or month_text


def _cell_paragraph(text: str) -> str:
    return (
        '<text:p text:style-name="Standard">'
        f"{xml_escape(_header_value(text))}"
        "</text:p>"
    )


def _table_cell(value: str, *, style: str = "PlanCell") -> str:
    return (
        '<table:table-cell office:value-type="string" '
        f'table:style-name="{style}">'
        f"{_cell_paragraph(value)}"
        "</table:table-cell>"
    )


def _header_cell(text: str) -> str:
    return (
        '<table:table-cell office:value-type="string" table:style-name="PlanHeaderCell">'
        f'<text:p text:style-name="PlanHeader">{xml_escape(text)}</text:p>'
        "</table:table-cell>"
    )


def _heading_paragraph(text: str, *, style: str) -> str:
    return (
        f'<text:p text:style-name="{style}">{xml_escape(text)}</text:p>'
    )


def _section_path(
    roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
    *,
    process_id: str,
    section_id: str,
) -> tuple[str, ...]:
    target = str(section_id or "").strip()
    wanted_process = str(process_id or "").strip()
    if not target:
        return ()

    def _walk(nodes, ancestors: tuple[str, ...]) -> tuple[str, ...] | None:
        for node in nodes:
            if node.node_type == KNOWLEDGE_NODE_SECTION:
                node_id = str(node.node_id or "").strip()
                label = _display(node.label) or node_id
                path = ancestors + (label,)
                if node_id == target:
                    return path
                found = _walk(node.children, path)
                if found is not None:
                    return found
            else:
                found = _walk(node.children, ancestors)
                if found is not None:
                    return found
        return None

    for process_node in roots:
        if str(process_node.process_id or "").strip() != wanted_process:
            continue
        found = _walk(process_node.children, ())
        if found:
            return found
    return ()


@dataclass(frozen=True)
class StatementPrintRow:
    number: int
    process_id: str
    process_name: str
    area_name: str
    section_name: str
    assertion_text: str
    verification_label: str


@dataclass(frozen=True)
class AuditProgramStatementsExportContext:
    program_label: str
    planned_period: str
    workplace_name: str
    document_status: str
    rows: tuple[StatementPrintRow, ...]

    def placeholder_values(self) -> dict[str, object]:
        return {
            "program_auditu": _header_value(self.program_label),
            "planovane_obdobi": _header_value(self.planned_period),
            "auditovany_provoz": _header_value(self.workplace_name),
            "stav_dokumentu": _header_value(self.document_status),
            "hodnoceni_legenda": self._legend_text(),
            "tvrzeni_obsah": self._statements_fragment(),
        }

    @staticmethod
    def _legend_text() -> str:
        return "\n".join(
            (
                AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_V,
                AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_VD,
                AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_N,
                AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_NP,
            )
        )

    def _statements_fragment(self) -> OdtXmlFragment:
        parts: list[str] = []
        current_process = None
        current_area = None
        current_section = None
        group_rows: list[StatementPrintRow] = []
        table_index = 0

        def flush() -> None:
            nonlocal table_index, group_rows
            if not group_rows:
                return
            table_index += 1
            parts.append(_build_statements_table(table_index, group_rows))
            group_rows = []

        for row in self.rows:
            process_key = (row.process_id, row.process_name)
            area_key = row.area_name
            section_key = row.section_name
            if process_key != current_process:
                flush()
                current_process = process_key
                current_area = None
                current_section = None
                parts.append(
                    _heading_paragraph(
                        f"{PROCESS_TERM_PROCESS}: {row.process_name}",
                        style="H",
                    )
                )
            if area_key != current_area:
                flush()
                current_area = area_key
                current_section = None
                parts.append(
                    _heading_paragraph(
                        f"{PROCESS_TERM_CRITERION}: {row.area_name}",
                        style="Standard",
                    )
                )
            if section_key and section_key != current_section:
                flush()
                current_section = section_key
                if section_key != area_key:
                    parts.append(
                        _heading_paragraph(f"Sekce: {row.section_name}", style="Standard")
                    )
            elif not section_key:
                current_section = ""
            group_rows.append(row)
        flush()
        return OdtXmlFragment(xml="".join(parts))


def _build_statements_table(index: int, rows: list[StatementPrintRow]) -> str:
    columns = "".join(
        f'<table:table-column table:style-name="{style}"/>'
        for style in (
            "StatementsColA",
            "StatementsColB",
            "StatementsColC",
            "StatementsColD",
            "StatementsColE",
        )
    )
    header_row = (
        '<table:table-header-rows><table:table-row table:style-name="PlanHeaderRow">'
        + "".join(
            _header_cell(item)
            for item in (
                "Č.",
                PROCESS_TERM_QUESTION,
                "Způsob ověření",
                "Výsledek",
                "Poznámka",
            )
        )
        + "</table:table-row></table:table-header-rows>"
    )
    body_rows: list[str] = []
    for row in rows:
        cells = "".join(
            (
                _table_cell(str(row.number)),
                _table_cell(row.assertion_text),
                _table_cell(row.verification_label),
                _table_cell(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_MARKS),
                _table_cell(""),
            )
        )
        body_rows.append(
            '<table:table-row table:style-name="PlanBodyRow">'
            + cells
            + "</table:table-row>"
        )
    return (
        f'<table:table table:name="Tvrzeni{index}" table:style-name="StatementsTable">'
        f"{columns}{header_row}{''.join(body_rows)}</table:table>"
    )


def _rows_from_items(
    items: list[tuple[str, str, str, str, str, str]],
    roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
) -> tuple[StatementPrintRow, ...]:
    rows: list[StatementPrintRow] = []
    number = 0
    for process_id, process_name, section_id, section_name, assertion_text, verification in items:
        text = _display(assertion_text)
        if not text:
            continue
        number += 1
        path = _section_path(roots, process_id=process_id, section_id=section_id)
        area_name = path[0] if path else (_display(section_name) or "—")
        nested = path[-1] if len(path) > 1 else ""
        if nested == area_name:
            nested = ""
        rows.append(
            StatementPrintRow(
                number=number,
                process_id=_display(process_id),
                process_name=_display(process_name) or _display(process_id) or "—",
                area_name=area_name,
                section_name=nested,
                assertion_text=text,
                verification_label=format_verification_type_label(verification),
            )
        )
    return tuple(rows)


def _items_from_drafts(
    drafts: list[AuditQuestionSnapshotDraft],
) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (
            draft.process_id,
            draft.process_name,
            draft.section_id,
            draft.section_name,
            draft.assertion_text,
            draft.verification_type,
        )
        for draft in drafts
    ]


def _items_from_views(
    views: tuple[SnapshotAssertionView, ...] | list[SnapshotAssertionView],
) -> list[tuple[str, str, str, str, str, str]]:
    return [
        (
            view.process_id,
            view.process_name,
            view.section_id,
            view.section_name,
            view.assertion_text,
            view.verification_type,
        )
        for view in views
        if view.is_in_scope
    ]


def _append_extraordinary_drafts(
    drafts: list[AuditQuestionSnapshotDraft],
    *,
    workplace_id: int,
) -> list[AuditQuestionSnapshotDraft]:
    with get_session() as session:
        assignments = (
            audit_extraordinary_assignment_service.require_assignable_for_workplace(
                session, int(workplace_id)
            )
        )
        order_start = EXTRAORDINARY_SNAPSHOT_ORDER_BASE
        if drafts:
            order_start = max(int(item.display_order) for item in drafts) + 1
            order_start = max(order_start, EXTRAORDINARY_SNAPSHOT_ORDER_BASE)
        extra = audit_extraordinary_assignment_service.build_snapshot_drafts(
            assignments,
            audit_id=0,
            display_order_start=order_start,
        )
    return list(drafts) + extra


class AuditProgramStatementsExportContextService:
    def build_for_visit(self, visit_id: int) -> AuditProgramStatementsExportContext:
        if visit_id is None or int(visit_id) <= 0:
            raise ValueError("Neplatná návštěva.")

        visit = audit_program_service.repository.get_visit(int(visit_id))
        if visit is None:
            raise ValueError("Návštěva nebyla nalezena.")
        program = audit_program_service.repository.get_program(visit.program_id)
        if program is None:
            raise ValueError("Auditní program nebyl nalezen.")

        workplace_name = audit_program_service._resolve_workplace_name(visit)
        program_label = _program_label(program.number, program.name)
        planned_period = _planned_period(visit.planned_year, visit.planned_month)

        if visit.audit_id is not None:
            return self._build_from_audit(
                visit.audit_id,
                program_label=program_label,
                planned_period=planned_period,
                workplace_name=workplace_name,
            )
        return self._build_from_current_methodology(
            visit,
            program_label=program_label,
            planned_period=planned_period,
            workplace_name=workplace_name,
        )

    def _build_from_audit(
        self,
        audit_id: int,
        *,
        program_label: str,
        planned_period: str,
        workplace_name: str,
    ) -> AuditProgramStatementsExportContext:
        audit = audit_service.get_by_id(int(audit_id))
        if audit is None:
            raise ValueError("Audit návštěvy nebyl nalezen.")
        source = audit_question_source_service.resolve_for_audit(int(audit_id), audit=audit)
        views = tuple(view for view in source.assertions if view.is_in_scope)
        roots = build_knowledge_tree_from_snapshot_views(views)
        rows = _rows_from_items(_items_from_views(views), roots)
        if not rows:
            raise AuditProgramStatementsEmptyError(AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY)
        number = _display(audit.number) or str(audit.id)
        return AuditProgramStatementsExportContext(
            program_label=program_label,
            planned_period=planned_period,
            workplace_name=workplace_name,
            document_status=AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN.format(
                number=number
            ),
            rows=rows,
        )

    def _build_from_current_methodology(
        self,
        visit,
        *,
        program_label: str,
        planned_period: str,
        workplace_name: str,
    ) -> AuditProgramStatementsExportContext:
        workplace_id = visit.workplace_id
        if workplace_id is None or int(workplace_id) <= 0:
            raise ValueError("Návštěva nemá přiřazený provoz.")

        system_workplace_id = (
            system_audit_workplace_service.require_system_audit_workplace_id()
        )
        planned_processes = audit_program_service.repository.list_visit_processes(visit.id)
        planned_process_ids = {
            str(item.process_id).strip()
            for item in planned_processes
            if str(item.process_id or "").strip()
        }
        knowledge_tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
        drafts = audit_question_snapshot_service.build_v2_preview_drafts(
            workplace_id=int(workplace_id),
            system_workplace_id=int(system_workplace_id),
            planned_process_ids=planned_process_ids,
            ensure=False,
            knowledge_tree=knowledge_tree,
        )
        drafts = _append_extraordinary_drafts(drafts, workplace_id=int(workplace_id))
        rows = _rows_from_items(_items_from_drafts(drafts), knowledge_tree)
        if not rows:
            raise AuditProgramStatementsEmptyError(AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY)
        return AuditProgramStatementsExportContext(
            program_label=program_label,
            planned_period=planned_period,
            workplace_name=workplace_name,
            document_status=AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT,
            rows=rows,
        )


audit_program_statements_export_context_service = (
    AuditProgramStatementsExportContextService()
)
