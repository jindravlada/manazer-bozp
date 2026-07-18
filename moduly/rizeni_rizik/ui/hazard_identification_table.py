from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from moduly.rizeni_rizik.constants import (
    COL_ID,
    COL_IDENTIFICATION,
    COL_OPERATION,
    COL_RESPONSIBLE_PERSON,
    COL_STARTED_AT,
    COL_STATUS,
    COL_WORKPLACE,
    COL_WORKPLACE_PART,
    COLUMN_COUNT,
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    TABLE_HEADERS,
)


class HazardIdentificationTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.setColumnHidden(COL_ID, True)
        self.setColumnHidden(COL_IDENTIFICATION, True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)

    def load_identifications(self, identifications) -> None:
        self.setRowCount(len(identifications))
        for row, identification in enumerate(identifications):
            self.setItem(row, COL_ID, QTableWidgetItem(str(identification.id)))
            self.setItem(
                row,
                COL_IDENTIFICATION,
                QTableWidgetItem(identification.identification_number or ""),
            )
            self.setItem(
                row,
                COL_OPERATION,
                QTableWidgetItem(identification.operation_name or ""),
            )
            self.setItem(
                row,
                COL_WORKPLACE,
                QTableWidgetItem(identification.workplace_name or ""),
            )
            self.setItem(
                row,
                COL_WORKPLACE_PART,
                QTableWidgetItem(identification.workplace_part_name or ""),
            )
            started_text = (
                identification.started_at.strftime("%d.%m.%Y")
                if identification.started_at is not None
                else ""
            )
            self.setItem(row, COL_STARTED_AT, QTableWidgetItem(started_text))
            self.setItem(
                row,
                COL_RESPONSIBLE_PERSON,
                QTableWidgetItem(identification.responsible_person_name or ""),
            )
            status_label = HAZARD_IDENTIFICATION_STATUS_LABELS.get(
                identification.status,
                identification.status,
            )
            status_item = QTableWidgetItem(status_label)
            if not identification.active:
                status_item.setForeground(Qt.GlobalColor.gray)
            self.setItem(row, COL_STATUS, status_item)

            for column in range(COLUMN_COUNT):
                item = self.item(row, column)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def selected_identification_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), COL_ID)
        return int(item.text()) if item else None
