from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from core.widgets.table_utils import apply_cell_tooltip
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    EMP_COL_ABBREVIATION,
    EMP_COL_ACTIVE,
    EMP_COL_ICO,
    EMP_COL_ID,
    EMP_COL_IS_MAIN,
    EMP_COL_NAME,
    EMP_COL_RISK_STATUS,
    EMP_COLUMN_COUNT,
    EMPLOYER_TABLE_HEADERS,
    RISK_HANDOVER_STATUS_LABELS,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    employer_abbreviation,
)
from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
    coordination_risk_submission_service,
)


class CoordinationEmployerTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(EMP_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(EMPLOYER_TABLE_HEADERS)
        self.setColumnHidden(EMP_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        enable_typed_sorting(self)

    def load_employers(self, employers) -> None:
        with sorting_paused(self):
            self.setRowCount(len(employers))
            for row, item in enumerate(employers):
                record_id = int(item.id)
                risk_status = coordination_risk_submission_service.handover_status(item.id)
                risk_label = RISK_HANDOVER_STATUS_LABELS.get(risk_status, risk_status)
                self.setItem(
                    row,
                    EMP_COL_ID,
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                )
                abbr = employer_abbreviation(item)
                self.setItem(
                    row,
                    EMP_COL_ABBREVIATION,
                    create_typed_item(
                        abbr,
                        typed_text(abbr),
                        stable_id=record_id,
                    ),
                )
                name_text = item.company_name or ""
                name_item = create_typed_item(
                    name_text,
                    typed_text(item.company_name),
                    stable_id=record_id,
                )
                apply_cell_tooltip(name_item, name_text)
                self.setItem(row, EMP_COL_NAME, name_item)
                self.setItem(
                    row,
                    EMP_COL_ICO,
                    create_typed_item(
                        item.ico or "",
                        typed_text(item.ico),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_IS_MAIN,
                    create_typed_item(
                        "Ano" if item.is_main else "Ne",
                        typed_bool(bool(item.is_main)),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    EMP_COL_RISK_STATUS,
                    create_typed_item(
                        risk_label,
                        typed_text(risk_label),
                        stable_id=record_id,
                    ),
                )
                active_item = create_typed_item(
                    "Ano" if item.active else "Ne",
                    typed_bool(bool(item.active)),
                    stable_id=record_id,
                )
                if not item.active:
                    active_item.setData(Qt.ItemDataRole.UserRole + 1, False)
                self.setItem(row, EMP_COL_ACTIVE, active_item)

    def selected_employer_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), EMP_COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
