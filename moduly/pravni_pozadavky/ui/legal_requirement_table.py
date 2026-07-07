from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_LABELS,
    legal_requirement_process_label,
    legal_requirement_responsible_label,
)

COL_ID = 0
COL_PROCESS = 1
COL_SUMMARY = 2
COL_RESPONSIBLE = 3
COL_STATUS = 4
COL_LAST_CHECK = 5
COL_NEXT_CHECK = 6
COL_PERIODICITY = 7
COLUMN_COUNT = 8


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalRequirementTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels([
            "ID",
            "Proces",
            "Způsob plnění",
            "Odpovědná osoba / funkce",
            "Stav plnění",
            "Poslední ověření",
            "Další ověření",
            "Periodicita",
        ])

        self.setColumnHidden(COL_ID, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_SUMMARY, QHeaderView.Stretch)
        for column in (
            COL_PROCESS,
            COL_RESPONSIBLE,
            COL_STATUS,
            COL_LAST_CHECK,
            COL_NEXT_CHECK,
            COL_PERIODICITY,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    def clear_selection(self) -> None:
        self.clearSelection()
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.clearCurrentIndex()

    def load_requirements(self, requirements) -> None:
        self.setRowCount(len(requirements))
        today = date.today()

        for row, requirement in enumerate(requirements):
            self._set_item(row, COL_ID, str(requirement.id))
            self._set_item(row, COL_PROCESS, legal_requirement_process_label(requirement))
            self._set_item(row, COL_SUMMARY, requirement.requirement_summary)
            self._set_item(row, COL_RESPONSIBLE, legal_requirement_responsible_label(requirement))
            self._set_item(
                row,
                COL_STATUS,
                COMPLIANCE_STATUS_LABELS.get(
                    requirement.compliance_status,
                    requirement.compliance_status,
                ),
            )
            self._set_item(row, COL_LAST_CHECK, _format_date(requirement.last_verification_date))
            self._set_item(row, COL_NEXT_CHECK, _format_date(requirement.next_verification_date))
            self._set_item(
                row,
                COL_PERIODICITY,
                PERIODICITY_LABELS.get(
                    requirement.verification_periodicity,
                    requirement.verification_periodicity,
                ),
            )

            self._apply_row_style(row, requirement, today)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

    def _apply_row_style(self, row: int, requirement, today: date) -> None:
        if not requirement.active:
            color = QColor("#f0f0f0")
        elif (
            requirement.next_verification_date is not None
            and requirement.next_verification_date < today
        ):
            color = QColor("#ffe0e0")
        else:
            color = None

        if color is None:
            return

        brush = QBrush(color)
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if item is not None:
                item.setBackground(brush)
