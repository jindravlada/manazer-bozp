from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.shared.risk_severity import RISK_SEVERITIES, RISK_SEVERITY_LABELS, format_risk_severity_tooltip
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.severity_tooltips import bind_severity_combo_tooltip
from moduly.rizeni_rizik.constants import RISK_MEASURE_FINDING_DIALOG_TITLE
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewError,
    risk_measure_review_service,
)


class RiskMeasureFindingDialog(QDialog):
    def __init__(self, parent=None, *, finding):
        super().__init__(parent)
        self.finding = finding
        self.setWindowTitle(f"{RISK_MEASURE_FINDING_DIALOG_TITLE} č. {finding.note_number}")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number_label = QLineEdit(finding.note_number or "")
        self.number_label.setReadOnly(True)
        self.title_edit = QLineEdit(finding.title or "")
        self.description = QPlainTextEdit(finding.description or "")
        self.description.setMinimumHeight(90)
        self.recommendation = QPlainTextEdit(finding.recommendation or "")
        self.recommendation.setMinimumHeight(90)
        self.severity = QComboBox()
        self.severity.addItem("—", "")
        for severity in RISK_SEVERITIES:
            self.severity.addItem(RISK_SEVERITY_LABELS[severity], severity)
            index = self.severity.count() - 1
            tooltip = format_risk_severity_tooltip(severity)
            if tooltip:
                self.severity.setItemData(index, tooltip, Qt.ItemDataRole.ToolTipRole)
        current = finding.severity if finding.severity in RISK_SEVERITIES else ""
        index = self.severity.findData(current)
        self.severity.setCurrentIndex(max(index, 0))
        bind_severity_combo_tooltip(self.severity)

        form.addRow("Číslo:", self.number_label)
        form.addRow("Název:", self.title_edit)
        form.addRow("Popis:", self.description)
        form.addRow("Doporučené opatření:", self.recommendation)
        form.addRow("Závažnost:", self.severity)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        try:
            updated = risk_measure_review_service.update_finding(
                self.finding.id,
                title=self.title_edit.text().strip(),
                description=self.description.toPlainText().strip(),
                recommendation=self.recommendation.toPlainText().strip(),
                severity=self.severity.currentData() or "",
            )
        except RiskMeasureReviewError as error:
            QMessageBox.warning(self, RISK_MEASURE_FINDING_DIALOG_TITLE, str(error))
            return
        if updated is None:
            QMessageBox.warning(
                self,
                RISK_MEASURE_FINDING_DIALOG_TITLE,
                "Zjištění nebylo nalezeno.",
            )
            return
        self.finding = updated
        super().accept()
