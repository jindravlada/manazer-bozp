"""Přehled plánovaných návštěv v manažeru programu auditů."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_status,
    typed_text,
)
from moduly.audity.constants import (
    AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM,
    AUDIT_PROGRAM_VISIT_STATUS_LABELS,
    AUDIT_PROGRAM_VISIT_STATUSES,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_visit_formatting import (
    format_planned_processes_cell,
    format_planned_term,
)

_COLUMN_TERM = 0
_COLUMN_WORKPLACE = 1
_COLUMN_PROCESSES = 2
_COLUMN_STATUS = 3
_COLUMN_AUDIT = 4
_COLUMN_AUDIT_MIN_WIDTH = 80


def _visit_status_sort(status: str):
    try:
        return typed_status(AUDIT_PROGRAM_VISIT_STATUSES.index(status), label=status or "")
    except ValueError:
        return typed_status(len(AUDIT_PROGRAM_VISIT_STATUSES), label=status or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class AuditProgramPlannedVisitsWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModulePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            [
                AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM,
                "Pracoviště",
                "Plánované procesy",
                "Stav",
                "Audit",
            ]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        enable_typed_sorting(self._table)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_COLUMN_TERM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COLUMN_WORKPLACE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COLUMN_PROCESSES, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(_COLUMN_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_COLUMN_AUDIT, QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(_COLUMN_PROCESSES, 240)
        self._table.setColumnWidth(_COLUMN_WORKPLACE, 200)
        self._table.setColumnWidth(_COLUMN_AUDIT, _COLUMN_AUDIT_MIN_WIDTH)
        layout.addWidget(self._table, 1)

    def load_program(self, program_id: int | None) -> None:
        if program_id is None:
            with sorting_paused(self._table):
                self._table.setRowCount(0)
            return

        rows = audit_program_service.get_planned_visits_overview(program_id)
        with sorting_paused(self._table):
            self._table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                record_id = int(row.visit_id)
                processes_text, processes_tooltip = format_planned_processes_cell(row.process_names)
                workplace = row.workplace_name or "—"
                status_label = AUDIT_PROGRAM_VISIT_STATUS_LABELS.get(row.status, row.status)
                audit_number = row.audit_number or "—"
                term_display = format_planned_term(
                    planned_date=row.planned_date,
                    planned_year=row.planned_year,
                    planned_month=row.planned_month,
                )
                term_item = create_typed_item(
                    term_display,
                    typed_date(row.sort_date) if row.sort_date is not None else typed_empty(),
                    stable_id=record_id,
                )
                term_item.setData(Qt.ItemDataRole.UserRole, row.visit_id)

                cells = [
                    term_item,
                    create_typed_item(
                        workplace,
                        _text_or_empty(workplace),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        processes_text,
                        typed_text(processes_text),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status_label,
                        _visit_status_sort(row.status),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        audit_number,
                        _text_or_empty(audit_number),
                        stable_id=record_id,
                    ),
                ]
                if processes_tooltip:
                    cells[_COLUMN_PROCESSES].setToolTip(processes_tooltip)
                for column_index, item in enumerate(cells):
                    self._table.setItem(row_index, column_index, item)

    def selected_visit_id(self) -> int | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        item = self._table.item(row, _COLUMN_TERM)
        if item is None:
            return None
        visit_id = item.data(Qt.ItemDataRole.UserRole)
        return int(visit_id) if visit_id is not None else None

    def set_selected_visit_id(self, visit_id: int | None) -> None:
        if visit_id is None:
            self._table.clearSelection()
            return

        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COLUMN_TERM)
            if item is None:
                continue
            if item.data(Qt.ItemDataRole.UserRole) == visit_id:
                self._table.selectRow(row)
                return
