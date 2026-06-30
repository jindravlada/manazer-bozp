from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, wrap_in_scroll_area
from moduly.vysetrovani_mu.sluzby.mu_investigation_check import (
    ACTION_TYPE_LABELS,
    CHECK_SEVERITY_ERROR,
    CHECK_SEVERITY_OK,
    CHECK_SEVERITY_RECOMMENDATION,
    CHECK_SEVERITY_WARNING,
    InvestigationCheckResult,
    PRIORITY_LABELS,
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
_NO_SUGGESTION_TEXT = "Pro tuto kontrolu není připraven doporučený pracovní krok."


class MuInvestigationCheckDialog(QDialog):
    def __init__(self, parent=None, *, snapshot: dict, investigation_id: int | None = None):
        super().__init__(parent)

        self.setWindowTitle("Kontrola spisu")
        configure_resizable_form_dialog(self, width=900, height=680, min_width=640, min_height=480)

        self._investigation_id = investigation_id
        self._results = run_investigation_checks(snapshot)
        self._navigation_result: InvestigationCheckResult | None = None
        self._tables: list[QTableWidget] = []

        layout = QVBoxLayout(self)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.addWidget(self._build_summary())

        for severity in SEVERITY_ORDER:
            group_results = [item for item in self._results if item.severity == severity]
            if not group_results:
                continue
            scroll_layout.addWidget(self._build_group(severity, group_results), 1)

        layout.addWidget(wrap_in_scroll_area(scroll_content), 1)
        layout.addWidget(self._build_suggestion_panel())
        layout.addWidget(self._build_buttons())

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

    def _build_suggestion_panel(self) -> QGroupBox:
        group = QGroupBox("Navržený další krok")
        layout = QVBoxLayout(group)

        self._suggestion_empty_label = QLabel(_NO_SUGGESTION_TEXT)
        self._suggestion_empty_label.setWordWrap(True)
        self._suggestion_empty_label.setObjectName("InfoText")

        self._suggestion_title_label = QLabel()
        self._suggestion_title_label.setWordWrap(True)
        self._suggestion_title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._suggestion_description_label = QLabel()
        self._suggestion_description_label.setWordWrap(True)
        self._suggestion_description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._suggestion_priority_label = QLabel()
        self._suggestion_type_label = QLabel()

        self._suggestion_details = QWidget()
        details_layout = QFormLayout(self._suggestion_details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addRow("Název:", self._suggestion_title_label)
        details_layout.addRow("Popis:", self._suggestion_description_label)
        details_layout.addRow("Priorita:", self._suggestion_priority_label)
        details_layout.addRow("Typ:", self._suggestion_type_label)

        self._create_action_btn = QPushButton("Vytvořit vyšetřovací úkon")
        self._create_action_btn.setVisible(False)
        self._create_action_btn.clicked.connect(self._create_investigation_action)

        actions_row = QHBoxLayout()
        actions_row.addStretch()
        actions_row.addWidget(self._create_action_btn)

        layout.addWidget(self._suggestion_empty_label)
        layout.addWidget(self._suggestion_details)
        layout.addLayout(actions_row)

        self._suggestion_details.setVisible(False)
        self._suggestion_empty_label.setText("Vyberte položku kontroly pro zobrazení doporučeného kroku.")
        return group

    def _build_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox()
        self._navigate_btn = QPushButton("Přejít")
        self._navigate_btn.setEnabled(False)
        self._navigate_btn.clicked.connect(self._navigate_to_selected)
        buttons.addButton(self._navigate_btn, QDialogButtonBox.ActionRole)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        close_btn.setText("Zavřít")
        buttons.rejected.connect(self.reject)
        return buttons

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
            if item.has_suggested_action():
                tooltip += f"\n\nNavržený krok: {item.suggested_task_title}"
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

        table.itemSelectionChanged.connect(lambda t=table: self._on_table_selection_changed(t))
        table.doubleClicked.connect(self._navigate_to_selected)
        self._tables.append(table)
        layout.addWidget(table)
        return group

    def _on_table_selection_changed(self, source_table: QTableWidget) -> None:
        if source_table.selectedItems():
            for table in self._tables:
                if table is source_table:
                    continue
                table.blockSignals(True)
                table.clearSelection()
                table.blockSignals(False)
        self._update_navigate_button()
        self._update_suggestion_panel()

    def _update_create_action_button(self) -> None:
        result = self._selected_result()
        can_show = (
            result is not None
            and result.can_create_task
            and self._investigation_id is not None
        )
        self._create_action_btn.setVisible(can_show)
        if can_show:
            self._create_action_btn.setEnabled(True)
            self._create_action_btn.setToolTip("")
        elif result is not None and result.can_create_task and self._investigation_id is None:
            self._create_action_btn.setVisible(True)
            self._create_action_btn.setEnabled(False)
            self._create_action_btn.setToolTip("Vyšetřování musí být nejdříve uloženo.")
        else:
            self._create_action_btn.setEnabled(False)
            self._create_action_btn.setToolTip("")

    def _create_investigation_action(self) -> None:
        result = self._selected_result()
        if result is None or not result.can_create_task or self._investigation_id is None:
            return

        from moduly.vysetrovani_mu.sluzby.mu_investigation_action_service import (
            mu_investigation_action_service,
        )

        try:
            create_result = mu_investigation_action_service.create_from_check_result(
                self._investigation_id,
                result,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Vyšetřovací úkon", str(exc))
            return

        if create_result.duplicate:
            answer = QMessageBox.question(
                self,
                "Vyšetřovací úkon",
                "Tento vyšetřovací úkon již existuje.\n\nChcete jej otevřít?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_task(create_result.task_id)
            return

        answer = QMessageBox.question(
            self,
            "Vyšetřovací úkon",
            "Vyšetřovací úkon byl vytvořen.\n\nOtevřít vytvořený úkon?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._open_task(create_result.task_id)

    def _open_task(self, task_id: int) -> None:
        from moduly.ukoly.sluzby.task_service import task_service
        from moduly.ukoly.ui.task_dialog import TaskDialog

        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, "Vyšetřovací úkon", "Úkon se nepodařilo načíst.")
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec():
            task_service.update_task(task_id=task_id, **dialog.get_data())

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

    def _update_suggestion_panel(self) -> None:
        result = self._selected_result()
        if result is None or not result.has_suggested_action():
            self._suggestion_empty_label.setVisible(True)
            self._suggestion_details.setVisible(False)
            if result is None:
                self._suggestion_empty_label.setText("Vyberte položku kontroly pro zobrazení doporučeného kroku.")
            else:
                self._suggestion_empty_label.setText(_NO_SUGGESTION_TEXT)
            self._update_create_action_button()
            return

        self._suggestion_empty_label.setVisible(False)
        self._suggestion_details.setVisible(True)
        self._suggestion_title_label.setText(result.suggested_task_title)
        self._suggestion_description_label.setText(result.suggested_task_description or "—")
        self._suggestion_priority_label.setText(
            PRIORITY_LABELS.get(result.suggested_priority, result.suggested_priority or "—")
        )
        self._suggestion_type_label.setText(
            ACTION_TYPE_LABELS.get(result.suggested_action_type, result.suggested_action_type or "—")
        )
        self._update_create_action_button()

    def _navigate_to_selected(self) -> None:
        result = self._selected_result()
        if not self._can_navigate(result):
            return
        self._navigation_result = result
        self.accept()
