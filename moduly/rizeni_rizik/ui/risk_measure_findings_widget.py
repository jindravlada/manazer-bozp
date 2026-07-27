from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_FINDING_COL_ID,
    RISK_MEASURE_FINDING_COL_NUMBER,
    RISK_MEASURE_FINDING_COL_RECOMMENDATION,
    RISK_MEASURE_FINDING_COL_SEVERITY,
    RISK_MEASURE_FINDING_COL_TITLE,
    RISK_MEASURE_FINDING_COLUMN_COUNT,
    RISK_MEASURE_FINDING_DIALOG_TITLE,
    RISK_MEASURE_FINDING_TABLE_HEADERS,
    RISK_MEASURE_FINDINGS_TITLE,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    risk_measure_review_service,
)
from moduly.rizeni_rizik.ui.risk_measure_finding_dialog import RiskMeasureFindingDialog


class RiskMeasureFindingsWidget(QWidget):
    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._review_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.hint = QLabel(
            "Zjištění vznikají podle čísel poznámek v checklistu. "
            "Podrobnosti doplňte po návratu do kanceláře."
        )
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        toolbar = QHBoxLayout()
        self.edit_btn = QPushButton("Upravit")
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(RISK_MEASURE_FINDING_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(RISK_MEASURE_FINDING_TABLE_HEADERS)
        self.table.setColumnHidden(RISK_MEASURE_FINDING_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        configure_table_columns(self.table, "risk_measure_findings")

        self.edit_btn.clicked.connect(self.edit_selected)
        self.table.doubleClicked.connect(self.edit_selected)

    def set_review_id(self, review_id: int | None) -> None:
        self._review_id = review_id
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if not self._review_id:
            return
        findings = risk_measure_review_service.list_findings(self._review_id)
        self.table.setRowCount(len(findings))
        for row_index, finding in enumerate(findings):
            self.table.setItem(
                row_index,
                RISK_MEASURE_FINDING_COL_ID,
                QTableWidgetItem(str(finding.id)),
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_FINDING_COL_NUMBER,
                QTableWidgetItem(finding.note_number or ""),
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_FINDING_COL_TITLE,
                create_preview_table_item(finding.title or ""),
            )
            severity_label = (
                format_risk_severity_label(finding.severity)
                if finding.severity
                else "—"
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_FINDING_COL_SEVERITY,
                QTableWidgetItem(severity_label),
            )
            self.table.setItem(
                row_index,
                RISK_MEASURE_FINDING_COL_RECOMMENDATION,
                create_preview_table_item(finding.recommendation or ""),
            )
        configure_table_columns(self.table, "risk_measure_findings")

    def edit_selected(self) -> None:
        finding_id = self._selected_finding_id()
        if finding_id is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_FINDINGS_TITLE,
                "Vyberte zjištění.",
            )
            return
        finding = risk_measure_review_service.get_finding(finding_id)
        if finding is None:
            QMessageBox.warning(
                self,
                RISK_MEASURE_FINDING_DIALOG_TITLE,
                "Zjištění nebylo nalezeno.",
            )
            self.refresh()
            return
        dialog = RiskMeasureFindingDialog(self, finding=finding)
        if dialog.exec():
            self.refresh()
            if callable(self._on_changed):
                self._on_changed()

    def open_by_note_number(self, note_number: str) -> None:
        if not self._review_id:
            return
        finding = risk_measure_review_service.ensure_finding_for_note_number(
            self._review_id,
            note_number,
        )
        self.refresh()
        if finding is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, RISK_MEASURE_FINDING_COL_NUMBER)
            if item is not None and item.text() == finding.note_number:
                self.table.selectRow(row)
                break

    def _selected_finding_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), RISK_MEASURE_FINDING_COL_ID)
        if item is None:
            return None
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None
