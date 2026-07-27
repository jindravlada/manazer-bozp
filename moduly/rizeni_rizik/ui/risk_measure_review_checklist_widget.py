from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
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
    RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER,
    RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
    RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT,
    RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
    RISK_MEASURE_REVIEW_NOTES_LINE_COUNT,
    RISK_MEASURE_REVIEW_NOTES_TITLE,
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
    """Kompaktní terénní checklist (A4): Vyhovuje / Poznámka č. / Foto."""

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

        self.notes_group = QGroupBox(RISK_MEASURE_REVIEW_NOTES_TITLE)
        self.notes_group.setObjectName("riskMeasureReviewNotes")
        notes_layout = QFormLayout(self.notes_group)
        notes_layout.setContentsMargins(8, 8, 8, 8)
        notes_layout.setSpacing(6)
        self.note_lines: list[QLineEdit] = []
        for index in range(1, RISK_MEASURE_REVIEW_NOTES_LINE_COUNT + 1):
            line = QLineEdit()
            line.setPlaceholderText("." * 44)
            line.setMaxLength(200)
            line.setClearButtonEnabled(False)
            line.setReadOnly(True)  # zatím jen rozvržení, ne DB
            line.setObjectName(f"riskMeasureReviewNoteLine{index}")
            notes_layout.addRow(f"Poznámka {index}", line)
            self.note_lines.append(line)
        layout.addWidget(self.notes_group)

        configure_table_columns(self.table, "risk_measure_review_items")

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        for row in range(self.table.rowCount()):
            for column in (
                RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
                RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
            ):
                host = self.table.cellWidget(row, column)
                checkbox = getattr(host, "_checkbox", None) if host is not None else None
                if isinstance(checkbox, QCheckBox):
                    checkbox.setEnabled(not self._read_only)
            note_number = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER)
            if isinstance(note_number, QLineEdit):
                note_number.setReadOnly(self._read_only)

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

            note_number = QLineEdit(row.note_number or "")
            note_number.setMaxLength(8)
            note_number.setPlaceholderText("____")
            note_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note_number.setReadOnly(self._read_only)
            note_number.textChanged.connect(self._emit_changed)
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER,
                note_number,
            )

            photo_host = _centered_checkbox(
                checked=bool(row.has_photo),
                enabled=not self._read_only,
                on_changed=self._emit_changed,
            )
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
                photo_host,
            )

            self.table.setRowHeight(row_index, 28)

        configure_table_columns(self.table, "risk_measure_review_items")

    def get_updates(self) -> list[dict]:
        updates: list[dict] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, RISK_MEASURE_REVIEW_ITEM_COL_ID)
            if id_item is None:
                continue
            compliant_host = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT)
            photo_host = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO)
            note_number = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE_NUMBER)
            compliant_box = getattr(compliant_host, "_checkbox", None)
            photo_box = getattr(photo_host, "_checkbox", None)
            updates.append(
                {
                    "item_id": int(id_item.text()),
                    "compliant": (
                        bool(compliant_box.isChecked())
                        if isinstance(compliant_box, QCheckBox)
                        else False
                    ),
                    "note_number": (
                        note_number.text().strip()
                        if isinstance(note_number, QLineEdit)
                        else ""
                    ),
                    "has_photo": (
                        bool(photo_box.isChecked())
                        if isinstance(photo_box, QCheckBox)
                        else False
                    ),
                }
            )
        return updates

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()
