"""Přehled plánovaných návštěv v manažeru programu auditů."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from moduly.audity.constants import (
    AUDIT_PROGRAM_PLANNED_VISITS_COLUMN_TERM,
    AUDIT_PROGRAM_VISIT_STATUS_LABELS,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.audit_program_visit_formatting import (
    format_planned_processes_cell,
    format_planned_term,
)

_SORT_ROLE = Qt.ItemDataRole.UserRole + 1
_COLUMN_TERM = 0
_COLUMN_WORKPLACE = 1
_COLUMN_PROCESSES = 2
_COLUMN_STATUS = 3
_COLUMN_AUDIT = 4
_COLUMN_AUDIT_MIN_WIDTH = 80


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
            self._table.setRowCount(0)
            return

        rows = audit_program_service.get_planned_visits_overview(program_id)
        self._table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            processes_text, processes_tooltip = format_planned_processes_cell(row.process_names)
            values = [
                format_planned_term(
                    planned_date=row.planned_date,
                    planned_year=row.planned_year,
                    planned_month=row.planned_month,
                ),
                row.workplace_name or "—",
                processes_text,
                AUDIT_PROGRAM_VISIT_STATUS_LABELS.get(row.status, row.status),
                row.audit_number or "—",
            ]
            sort_key = row.sort_date.toordinal() if row.sort_date is not None else 99999999

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column_index == _COLUMN_TERM:
                    item.setData(_SORT_ROLE, sort_key)
                    item.setData(Qt.ItemDataRole.UserRole, row.visit_id)
                if column_index == _COLUMN_PROCESSES and processes_tooltip:
                    item.setToolTip(processes_tooltip)
                self._table.setItem(row_index, column_index, item)

        self._table.sortItems(_COLUMN_TERM, Qt.SortOrder.AscendingOrder)

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
