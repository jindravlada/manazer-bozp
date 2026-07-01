from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_PROVERKY
from core.shared.finding_display import (
    finding_status_background,
    finding_status_label,
    finding_status_text_color,
    finding_type_label,
)
from core.shared.sluzby.finding_service import finding_service
from core.widgets.finding_dialog import FindingDialog
from core.widgets.finding_summary_panel import FindingSummaryPanel
from core.widgets.finding_task_actions import FindingTaskActions
from moduly.proverky.constants import FINDING_DIALOG_TITLE


class BozpInspectionFindingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.inspection_id: int | None = None
        self._on_task_changed = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Zjištění lze přidat až po uložení prověrky.")
        self.info_label.setWordWrap(True)

        self.summary_panel = FindingSummaryPanel()

        toolbar = QHBoxLayout()
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        self.task_actions = FindingTaskActions(
            self,
            self._selected_finding_id,
            self._after_task_action,
        )
        toolbar.addWidget(self.task_actions.button)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Poř.",
            "Typ",
            "Oblast",
            "Sekce",
            "Kontrolní bod",
            "Reference",
            "Popis",
            "Stav",
        ])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        for column in (1, 2, 3, 4, 5, 6, 8):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.content_stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        self.empty_label = QLabel("Prověrka zatím neobsahuje žádné zjištění.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        self.table_page = QWidget()
        table_layout = QVBoxLayout(self.table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)

        self.content_stack.addWidget(self.empty_page)
        self.content_stack.addWidget(self.table_page)

        layout.addWidget(self.info_label)
        layout.addWidget(self.summary_panel)
        layout.addLayout(toolbar)
        layout.addWidget(self.content_stack, 1)

        self.edit_btn.clicked.connect(self.edit_finding)
        self.delete_btn.clicked.connect(self.delete_finding)
        self.table.doubleClicked.connect(self.edit_finding)
        self.table.itemSelectionChanged.connect(self.task_actions.update_state)

        self._update_state()
        self.task_actions.update_state()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.inspection_id = inspection_id
        self.refresh()
        self._update_state()

    def set_on_task_changed(self, callback) -> None:
        self._on_task_changed = callback

    def refresh(self) -> None:
        findings = []
        summary = {"total": 0}

        if self.inspection_id is not None:
            findings = finding_service.get_for_entity(ENTITY_PROVERKY, self.inspection_id)
            summary = finding_service.summarize(ENTITY_PROVERKY, self.inspection_id)

        self.summary_panel.update_summary(summary)
        self.summary_panel.setVisible(self.inspection_id is not None)
        self.content_stack.setCurrentIndex(1 if findings else 0)
        self.empty_label.setText(
            "Prověrka zatím neobsahuje žádné zjištění."
            if self.inspection_id is not None
            else "Zjištění lze zobrazit až po uložení prověrky."
        )

        self.table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            tooltip = self._finding_tooltip(finding)
            values = [
                str(finding.id),
                str(finding.display_order),
                finding_type_label(finding.finding_type),
                finding.source_area_label or "—",
                finding.source_section_label or "—",
                finding.source_control_point_label or "—",
                finding.reference_label or "—",
                self._text_preview(finding.description),
                finding_status_label(finding.status),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                if column == 8:
                    item.setBackground(QBrush(QColor(finding_status_background(finding.status))))
                    item.setForeground(QBrush(QColor(finding_status_text_color(finding.status))))
                self.table.setItem(row, column, item)

        self.task_actions.update_state()

    def _after_task_action(self) -> None:
        self.refresh()
        if self._on_task_changed is not None:
            self._on_task_changed()

    def _update_state(self) -> None:
        enabled = self.inspection_id is not None
        self.info_label.setVisible(not enabled)
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def _selected_finding_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_finding(self) -> None:
        finding_id = self._selected_finding_id()
        if finding_id is None:
            QMessageBox.information(self, "Zjištění", "Vyberte zjištění.")
            return

        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            QMessageBox.warning(self, "Zjištění", "Zjištění nebylo nalezeno.")
            self.refresh()
            return

        dialog = FindingDialog(
            self,
            finding=finding,
            title=FINDING_DIALOG_TITLE,
            knowledge_source={
                "source_label": "Prověrka BOZP",
                "area_label": finding.source_area_label or "—",
                "section_label": finding.source_section_label or "—",
                "control_point_label": finding.source_control_point_label or finding.reference_label or "—",
            },
        )
        if dialog.exec():
            finding_service.update(finding_id, **dialog.get_data())
            self.refresh()

    def delete_finding(self) -> None:
        finding_id = self._selected_finding_id()
        if finding_id is None:
            QMessageBox.information(self, "Zjištění", "Vyberte zjištění.")
            return

        answer = QMessageBox.question(
            self,
            "Smazat zjištění",
            "Opravdu smazat vybrané zjištění?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            finding_service.delete(finding_id)
            self.refresh()

    @staticmethod
    def _text_preview(text: str, max_len: int = 80) -> str:
        value = (text or "").strip()
        if not value:
            return "—"
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _finding_tooltip(finding) -> str:
        lines = [
            f"Typ: {finding_type_label(finding.finding_type)}",
            f"Oblast: {finding.source_area_label or '—'}",
            f"Sekce: {finding.source_section_label or '—'}",
            f"Kontrolní bod: {finding.source_control_point_label or '—'}",
            f"Reference: {finding.reference_label or '—'}",
            f"Popis: {finding.description or '—'}",
            f"Stav: {finding_status_label(finding.status)}",
        ]
        return "\n".join(lines)
