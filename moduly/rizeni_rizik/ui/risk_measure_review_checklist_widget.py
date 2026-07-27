from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_CHECKLIST_EMPTY,
    RISK_MEASURE_REVIEW_ITEM_COL_ID,
    RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
    RISK_MEASURE_REVIEW_ITEM_COL_NOTE,
    RISK_MEASURE_REVIEW_ITEM_COL_RESULT,
    RISK_MEASURE_REVIEW_ITEM_COL_RISK,
    RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_LABELS,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    RISK_MEASURE_REVIEW_ITEM_RESULTS,
    RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
)


class RiskMeasureReviewChecklistWidget(QWidget):
    """Editovatelná tabulka checklistu přezkoumání (bez ručního přidávání)."""

    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.empty_label = QLabel(RISK_MEASURE_REVIEW_CHECKLIST_EMPTY)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget()
        self.table.setColumnCount(RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.table.setColumnHidden(RISK_MEASURE_REVIEW_ITEM_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        configure_table_columns(self.table, "risk_measure_review_items")

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_RESULT)
            if isinstance(combo, QComboBox):
                combo.setEnabled(not self._read_only)
            note = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE)
            if isinstance(note, QLineEdit):
                note.setReadOnly(self._read_only)

    def load_rows(self, rows) -> None:
        self.table.setRowCount(0)
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        if not rows:
            return

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.table.setItem(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_ID,
                QTableWidgetItem(str(row.item_id)),
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_RISK,
                create_preview_table_item(row.risk_label),
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
                create_preview_table_item(row.measure_title),
            )

            result_combo = QComboBox()
            for result in RISK_MEASURE_REVIEW_ITEM_RESULTS:
                result_combo.addItem(RISK_MEASURE_REVIEW_ITEM_RESULT_LABELS[result], result)
            index = result_combo.findData(row.result)
            if index < 0:
                index = result_combo.findData(RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED)
            result_combo.setCurrentIndex(max(index, 0))
            result_combo.setEnabled(not self._read_only)
            result_combo.currentIndexChanged.connect(self._emit_changed)
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_RESULT,
                result_combo,
            )

            note_edit = QLineEdit(row.note or "")
            note_edit.setReadOnly(self._read_only)
            note_edit.textChanged.connect(self._emit_changed)
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_NOTE,
                note_edit,
            )

        configure_table_columns(self.table, "risk_measure_review_items")

    def get_updates(self) -> list[dict]:
        updates: list[dict] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, RISK_MEASURE_REVIEW_ITEM_COL_ID)
            if id_item is None:
                continue
            result_combo = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_RESULT)
            note_edit = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE)
            updates.append(
                {
                    "item_id": int(id_item.text()),
                    "result": (
                        result_combo.currentData()
                        if isinstance(result_combo, QComboBox)
                        else RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
                    ),
                    "note": note_edit.text().strip() if isinstance(note_edit, QLineEdit) else "",
                }
            )
        return updates

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()
