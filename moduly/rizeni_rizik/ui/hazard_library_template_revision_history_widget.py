from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_REVISION_HISTORY_COL_CREATED_AT,
    HAZARD_LIBRARY_REVISION_HISTORY_COL_NUMBER,
    HAZARD_LIBRARY_REVISION_HISTORY_COL_REASON,
    HAZARD_LIBRARY_REVISION_HISTORY_COLUMN_COUNT,
    HAZARD_LIBRARY_REVISION_HISTORY_EMPTY,
    HAZARD_LIBRARY_REVISION_HISTORY_HEADERS,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_revision_service import (
    hazard_library_template_revision_service,
)


class HazardLibraryTemplateRevisionHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._template_id: int | None = None

        layout = QVBoxLayout(self)
        self.empty_label = QLabel(HAZARD_LIBRARY_REVISION_HISTORY_EMPTY)
        self.empty_label.setWordWrap(True)
        self.table = QTableWidget()
        self.table.setColumnCount(HAZARD_LIBRARY_REVISION_HISTORY_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_LIBRARY_REVISION_HISTORY_HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

    def set_template_id(self, template_id: int | None) -> None:
        self._template_id = template_id
        self.refresh()

    def refresh(self) -> None:
        if self._template_id is None:
            self.table.setRowCount(0)
            self.empty_label.setVisible(True)
            self.table.setVisible(False)
            return

        rows = hazard_library_template_revision_service.get_rows(self._template_id)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_REVISION_HISTORY_COL_NUMBER,
                QTableWidgetItem(str(row.revision_number)),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_REVISION_HISTORY_COL_CREATED_AT,
                QTableWidgetItem(row.created_at.strftime("%d.%m.%Y %H:%M")),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_REVISION_HISTORY_COL_REASON,
                QTableWidgetItem(row.reason_label),
            )

        has_rows = len(rows) > 0
        self.empty_label.setVisible(not has_rows)
        self.table.setVisible(has_rows)
