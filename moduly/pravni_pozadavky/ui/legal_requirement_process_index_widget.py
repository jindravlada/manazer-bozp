"""Read-only záložka Index procesu — rozpad oblastí a vah."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
    PROCESS_INDEX_PLACEHOLDER,
    ProcessIndexBreakdown,
    legal_requirement_process_status_service,
)


def _format_index_number(value: float | None) -> str:
    if value is None:
        return PROCESS_INDEX_PLACEHOLDER
    return f"{value:.1f}".replace(".", ",")


class LegalRequirementProcessIndexWidget(QWidget):
    def __init__(self, requirement_id: int | None = None, parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Index procesu")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)

        intro = QLabel(
            "Rozpad oblastí, ze kterých se bude skládat budoucí Index procesu."
        )
        intro.setObjectName("InfoText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Oblast", "Váha (%)", "Skóre", "Přínos"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        self.total_weight_label = QLabel()
        self.index_label = QLabel()
        index_font = QFont(self.index_label.font())
        index_font.setBold(True)
        self.index_label.setFont(index_font)
        footer_layout.addWidget(self.total_weight_label)
        footer_layout.addWidget(self.index_label)
        layout.addWidget(footer)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        self.refresh()

    def refresh(self) -> None:
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self.requirement_id,
        )
        self._fill_table(breakdown)
        self.total_weight_label.setText(f"Součet vah: {breakdown.total_weight_percent} %")
        index_text = (
            PROCESS_INDEX_PLACEHOLDER
            if breakdown.index_value is None
            else _format_index_number(breakdown.index_value)
        )
        self.index_label.setText(f"Index procesu:\n{index_text}")

    def _fill_table(self, breakdown: ProcessIndexBreakdown) -> None:
        self.table.setRowCount(len(breakdown.areas))
        for row, area in enumerate(breakdown.areas):
            values = (
                area.area_label,
                str(area.weight_percent),
                _format_index_number(area.score),
                _format_index_number(area.contribution),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)
