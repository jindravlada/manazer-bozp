from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from moduly.vysetrovani_mu.sluzby.mu_investigation_check import (
    CHECK_SEVERITY_ERROR,
    CHECK_SEVERITY_OK,
    CHECK_SEVERITY_RECOMMENDATION,
    CHECK_SEVERITY_WARNING,
    InvestigationCheckResult,
    SEVERITY_LABELS,
    SEVERITY_ORDER,
    run_investigation_checks,
)

_SEVERITY_COLORS = {
    CHECK_SEVERITY_OK: ("#e8f5e9", "#2e7d32"),
    CHECK_SEVERITY_WARNING: ("#fff8e1", "#f57f17"),
    CHECK_SEVERITY_RECOMMENDATION: ("#e3f2fd", "#1565c0"),
    CHECK_SEVERITY_ERROR: ("#ffebee", "#c62828"),
}


class MuInvestigationCheckDialog(QDialog):
    def __init__(self, parent=None, *, snapshot: dict):
        super().__init__(parent)

        self.setWindowTitle("Kontrola spisu")
        self.resize(980, 640)

        self._results = run_investigation_checks(snapshot)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_summary())

        for severity in SEVERITY_ORDER:
            group_results = [item for item in self._results if item.severity == severity]
            if not group_results:
                continue
            layout.addWidget(self._build_group(severity, group_results), 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("Zavřít")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_summary(self) -> QLabel:
        counts = {severity: 0 for severity in SEVERITY_ORDER}
        for item in self._results:
            counts[item.severity] = counts.get(item.severity, 0) + 1

        parts = [
            f"{SEVERITY_LABELS[severity]}: {counts[severity]}"
            for severity in SEVERITY_ORDER
            if counts[severity]
        ]
        label = QLabel(" | ".join(parts) if parts else "Kontrola neobsahuje žádné položky.")
        label.setWordWrap(True)
        return label

    def _build_group(self, severity: str, results: list[InvestigationCheckResult]) -> QGroupBox:
        group = QGroupBox(SEVERITY_LABELS[severity])
        layout = QVBoxLayout(group)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Stav", "Název", "Popis", "Záložka"])
        table.setRowCount(len(results))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        bg, fg = _SEVERITY_COLORS.get(severity, ("#ffffff", "#000000"))
        for row, item in enumerate(results):
            values = [
                SEVERITY_LABELS[item.severity],
                item.title,
                item.message,
                item.tab_name,
            ]
            tooltip = item.message
            if item.suggested_task_title:
                tooltip += f"\n\nNavržený úkol: {item.suggested_task_title}"
            if item.suggested_task_description:
                tooltip += f"\n{item.suggested_task_description}"

            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(tooltip)
                cell.setBackground(QBrush(QColor(bg)))
                cell.setForeground(QBrush(QColor(fg)))
                if column in (2, 3):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                table.setItem(row, column, cell)

        layout.addWidget(table)
        return group
