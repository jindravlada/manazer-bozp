from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
    RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_COL_NOTE,
    RISK_MEASURE_REVIEW_ITEM_COL_PHOTO,
    RISK_MEASURE_REVIEW_ITEM_COLUMN_COUNT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
    RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
)
from moduly.rizeni_rizik.ui.risk_measure_review_item_photos_dialog import (
    RiskMeasureReviewItemPhotosDialog,
)


def _centered_checkbox(*, checked: bool, enabled: bool) -> QWidget:
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    checkbox = QCheckBox()
    checkbox.setChecked(checked)
    checkbox.setEnabled(enabled)
    layout.addWidget(checkbox)
    host._checkbox = checkbox  # noqa: SLF001 – přístup z widgetu tabulky
    return host


def _photo_button_label(count: int) -> str:
    if count <= 0:
        return "📷"
    return f"📷 ({count})"


class RiskMeasureReviewChecklistWidget(QWidget):
    """Checklist: opatření / Vyhovuje / Nevyhovuje / Foto / Poznámka."""

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
            for column in (
                RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
                RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
            ):
                host = self.table.cellWidget(row, column)
                checkbox = getattr(host, "_checkbox", None) if host is not None else None
                if isinstance(checkbox, QCheckBox):
                    checkbox.setEnabled(not self._read_only)
            note_edit = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE)
            if isinstance(note_edit, QPlainTextEdit):
                note_edit.setReadOnly(self._read_only)
            photo_btn = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO)
            if isinstance(photo_btn, QPushButton):
                photo_btn.setEnabled(not self._read_only)

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
                checked=row.result == RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                enabled=not self._read_only,
            )
            non_compliant_host = _centered_checkbox(
                checked=row.result == RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                enabled=not self._read_only,
            )
            self._wire_exclusive_checkboxes(compliant_host, non_compliant_host)
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT,
                compliant_host,
            )
            self.table.setCellWidget(
                row_index,
                RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
                non_compliant_host,
            )

            photo_btn = QPushButton(_photo_button_label(int(row.photo_count or 0)))
            photo_btn.setEnabled(not self._read_only)
            photo_btn._photo_count = int(row.photo_count or 0)  # noqa: SLF001
            photo_btn.clicked.connect(
                lambda _checked=False, r=row_index: self._open_photos(r)
            )
            self.table.setCellWidget(row_index, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO, photo_btn)

            note_edit = QPlainTextEdit(row.note or "")
            note_edit.setPlaceholderText("Poznámka z kontroly…")
            note_edit.setReadOnly(self._read_only)
            note_edit.setMaximumHeight(72)
            note_edit.setTabChangesFocus(True)
            note_edit.textChanged.connect(self._emit_changed)
            self.table.setCellWidget(row_index, RISK_MEASURE_REVIEW_ITEM_COL_NOTE, note_edit)

            self.table.setRowHeight(row_index, 78)

        configure_table_columns(self.table, "risk_measure_review_items")

    def get_updates(self) -> list[dict]:
        updates: list[dict] = []
        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, RISK_MEASURE_REVIEW_ITEM_COL_ID)
            if id_item is None:
                continue
            compliant_host = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_COMPLIANT)
            non_compliant_host = self.table.cellWidget(
                row,
                RISK_MEASURE_REVIEW_ITEM_COL_NON_COMPLIANT,
            )
            note_edit = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_NOTE)
            photo_btn = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO)
            compliant_box = getattr(compliant_host, "_checkbox", None)
            non_compliant_box = getattr(non_compliant_host, "_checkbox", None)
            compliant = (
                bool(compliant_box.isChecked())
                if isinstance(compliant_box, QCheckBox)
                else False
            )
            non_compliant = (
                bool(non_compliant_box.isChecked())
                if isinstance(non_compliant_box, QCheckBox)
                else False
            )
            if compliant:
                result = RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
            elif non_compliant:
                result = RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT
            else:
                result = RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
            photo_count = int(getattr(photo_btn, "_photo_count", 0) or 0)
            updates.append(
                {
                    "item_id": int(id_item.text()),
                    "result": result,
                    "compliant": compliant,
                    "non_compliant": non_compliant,
                    "note": (
                        note_edit.toPlainText().strip()
                        if isinstance(note_edit, QPlainTextEdit)
                        else ""
                    ),
                    "photo_count": photo_count,
                    "has_photo": photo_count > 0,
                }
            )
        return updates

    def _wire_exclusive_checkboxes(self, compliant_host: QWidget, non_compliant_host: QWidget) -> None:
        compliant_box = compliant_host._checkbox
        non_compliant_box = non_compliant_host._checkbox

        def on_compliant(state: int) -> None:
            if state == Qt.CheckState.Checked.value or state == Qt.CheckState.Checked:
                non_compliant_box.blockSignals(True)
                non_compliant_box.setChecked(False)
                non_compliant_box.blockSignals(False)
            self._emit_changed()

        def on_non_compliant(state: int) -> None:
            if state == Qt.CheckState.Checked.value or state == Qt.CheckState.Checked:
                compliant_box.blockSignals(True)
                compliant_box.setChecked(False)
                compliant_box.blockSignals(False)
            self._emit_changed()

        compliant_box.stateChanged.connect(on_compliant)
        non_compliant_box.stateChanged.connect(on_non_compliant)

    def _open_photos(self, row: int) -> None:
        id_item = self.table.item(row, RISK_MEASURE_REVIEW_ITEM_COL_ID)
        if id_item is None:
            return
        dialog = RiskMeasureReviewItemPhotosDialog(self, item_id=int(id_item.text()))
        dialog.exec()
        count = dialog.photo_count()
        photo_btn = self.table.cellWidget(row, RISK_MEASURE_REVIEW_ITEM_COL_PHOTO)
        if isinstance(photo_btn, QPushButton):
            photo_btn.setText(_photo_button_label(count))
            photo_btn._photo_count = count  # noqa: SLF001
        self._emit_changed()

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()
