from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QPushButton,
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

_RESULT_ROLE = Qt.ItemDataRole.UserRole


class MuInvestigationCheckDialog(QDialog):
    def __init__(self, parent=None, *, snapshot: dict):
        super().__init__(parent)

        self.setWindowTitle("Kontrola spisu")
        self.resize(980, 640)

        self._results = run_investigation_checks(snapshot)
        self._navigation_result: InvestigationCheckResult | None = None
        self._tables: list[QTableWidget] = []

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_summary())

        for severity in SEVERITY_ORDER:
            group_results = [item for item in self._results if item.severity == severity]
            if not group_results:
                continue
            layout.addWidget(self._build_group(severity, group_results), 1)

        buttons = QDialogButtonBox()
        self._navigate_btn = QPushButton("Přejít")
        self._navigate_btn.setEnabled(False)
        self._navigate_btn.clicked.connect(self._navigate_to_selected)
        buttons.addButton(self._navigate_btn, QDialogButtonBox.ActionRole)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.setText("Zavřít")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def navigation_result(self) -> InvestigationCheckResult | None:
        return self._navigation_result

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
                item.navigate_tab or item.tab_name,
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
                if column == 0:
                    cell.setData(_RESULT_ROLE, item)
                if column in (2, 3):
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                table.setItem(row, column, cell)

        table.itemSelectionChanged.connect(self._update_navigate_button)
        table.doubleClicked.connect(self._navigate_to_selected)
        self._tables.append(table)
        layout.addWidget(table)
        return group

    def _selected_result(self) -> InvestigationCheckResult | None:
        for table in self._tables:
            selected = table.selectedItems()
            if not selected:
                continue
            result = selected[0].data(_RESULT_ROLE)
            if isinstance(result, InvestigationCheckResult):
                return result
        return None

    def _can_navigate(self, result: InvestigationCheckResult | None) -> bool:
        return result is not None and bool(result.navigate_tab or result.tab_name)

    def _update_navigate_button(self) -> None:
        self._navigate_btn.setEnabled(self._can_navigate(self._selected_result()))

    def _navigate_to_selected(self) -> None:
        result = self._selected_result()
        if not self._can_navigate(result):
            return
        self._navigation_result = result
        self.accept()
