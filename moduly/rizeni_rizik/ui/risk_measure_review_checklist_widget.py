from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_CHECKLIST_EMPTY,
    RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_COL_ID,
    RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
    RISK_MEASURE_REVIEW_ITEM_COL_RESULT_TEXT,
    RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT,
    RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
)


def _centered_checkbox(*, checked: bool, enabled: bool, on_changed) -> QWidget:
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    checkbox = QCheckBox()
    checkbox.setChecked(checked)
    checkbox.setEnabled(enabled)
    checkbox.stateChanged.connect(on_changed)
    layout.addWidget(checkbox)
    host._checkbox = checkbox  # noqa: SLF001 – přístup z widgetu tabulky
    return host


class RiskMeasureReviewChecklistWidget(QWidget):
    """Checklist provedení: Navazující opatření / Vyhovuje / Výsledek přezkoumání."""

    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._read_only = False
        self.setObjectName("riskMeasureReviewChecklist")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.empty_label = QLabel(RISK_MEASURE_REVIEW_CHECKLIST_EMPTY)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget()
        self.table.setObjectName("riskMeasureReviewChecklistTable")
        self.table.setColumnCount(RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS)
        self.table.setColumnHidden(RISK_MEASURE_REVIEW_ITEM_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setWordWrap(True)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.table)

        configure_table_columns(self.table, "risk_measure_review_items")

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        for row in range(self.table.rowCount()):
            host = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT)
            checkbox = getattr(host, "_checkbox", None) if host is not None else None
            if isinstance(checkbox, QCheckBox):
                checkbox.setEnabled(not self._read_only)
            result_edit = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_RESULT_TEXT)
            if isinstance(result_edit, QLineEdit):
                result_edit.setReadOnly(self._read_only)

    def load_rows(self, rows) -> None:
        self.table.setRowCount(0)
        self.empty_label.setVisible(not rows)
        self.table.setVisible(bool(rows))
        if not rows:
            configure_table_columns(self.table, "risk_measure_review_items")
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
                RISK_MEASURE_REVIEW_ITEM_COL_MEASURE,
                create_preview_table_item(row.measure_title),
            )

            compliant_host = _centered_checkbox(
                checked=bool(row.compliant),
                enabled=not self._read_only,
                on_changed=self._emit_changed,
            )
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
                compliant_host,
            )

            result_edit = QLineEdit(row.result_text or "")
            result_edit.setPlaceholderText("Výsledek…")
            result_edit.setReadOnly(self._read_only)
            result_edit.textChanged.connect(self._emit_changed)
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_RESULT_TEXT,
                result_edit,
            )

            self.table.setRowHeight(row_index, 30)

        configure_table_columns(self.table, "risk_measure_review_items")

    def get_updates(self) -> list[dict]:
        updates: list[dict] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, RISK_MEASURE_REVIEW_ITEM_COL_ID)
            if id_item is None:
                continue
            compliant_host = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT)
            result_edit = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_RESULT_TEXT)
            compliant_box = getattr(compliant_host, "_checkbox", None)
            updates.append(
                {
                    "item_id": int(id_item.text()),
                    "compliant": (
                        bool(compliant_box.isChecked())
                        if isinstance(compliant_box, QCheckBox)
                        else False
                    ),
                    "result_text": (
                        result_edit.text().strip()
                        if isinstance(result_edit, QLineEdit)
                        else ""
                    ),
                }
            )
        return updates

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()
