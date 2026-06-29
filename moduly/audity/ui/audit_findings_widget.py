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

from core.shared.constants import ENTITY_AUDITY
from core.shared.finding_display import (
    finding_status_background,
    finding_status_label,
    finding_status_text_color,
    finding_type_label,
)
from core.shared.sluzby.finding_service import finding_service
from core.widgets.finding_dialog import FindingDialog
from core.widgets.finding_summary_panel import FindingSummaryPanel


class AuditFindingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit_id: int | None = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Zjištění lze přidat až po uložení auditu.")
        self.info_label.setWordWrap(True)

        self.summary_panel = FindingSummaryPanel()

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Poř.",
            "Typ",
            "Reference",
            "Popis",
            "Odpovědná osoba",
            "Termín",
            "Stav",
        ])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.content_stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        self.empty_label = QLabel("Audit zatím neobsahuje žádné zjištění.")
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

        self.add_btn.clicked.connect(self.add_finding)
        self.edit_btn.clicked.connect(self.edit_finding)
        self.delete_btn.clicked.connect(self.delete_finding)
        self.table.doubleClicked.connect(self.edit_finding)

        self._update_state()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.audit_id = audit_id
        self.refresh()
        self._update_state()

    def refresh(self) -> None:
        findings = []
        summary = {"total": 0}

        if self.audit_id is not None:
            findings = finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
            summary = finding_service.summarize(ENTITY_AUDITY, self.audit_id)

        self.summary_panel.update_summary(summary)
        self.summary_panel.setVisible(self.audit_id is not None)

        if self.audit_id is not None and not findings:
            self.content_stack.setCurrentWidget(self.empty_page)
        else:
            self.content_stack.setCurrentWidget(self.table_page)

        self.table.setRowCount(len(findings))
        for row, finding in enumerate(findings):
            values = [
                str(finding.id),
                str(finding.display_order),
                finding_type_label(finding.finding_type),
                finding.reference_label or "—",
                self._text_preview(finding.description),
                finding.responsible_person_name or "—",
                "" if finding.due_date is None else finding.due_date.strftime("%d.%m.%Y"),
                finding_status_label(finding.status),
            ]

            tooltip = self._finding_tooltip(finding)

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)

                if column == 7:
                    item.setBackground(QBrush(QColor(finding_status_background(finding.status))))
                    item.setForeground(QBrush(QColor(finding_status_text_color(finding.status))))

                self.table.setItem(row, column, item)

    def _text_preview(self, text: str, max_len: int = 80) -> str:
        value = (text or "").strip()
        if not value:
            return "—"
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"

    def _finding_tooltip(self, finding) -> str:
        lines = [
            f"Typ: {finding_type_label(finding.finding_type)}",
            f"Reference: {finding.reference_label or '—'}",
            f"Popis: {finding.description or '—'}",
            f"Doporučené opatření: {finding.recommended_action or '—'}",
            f"Odpovědná osoba: {finding.responsible_person_name or '—'}",
            f"Termín: {finding.due_date.strftime('%d.%m.%Y') if finding.due_date else '—'}",
            f"Stav: {finding_status_label(finding.status)}",
        ]
        if finding.resolution_note:
            lines.append(f"Poznámka k vypořádání: {finding.resolution_note}")
        return "\n".join(lines)

    def _update_state(self) -> None:
        enabled = self.audit_id is not None
        self.info_label.setVisible(not enabled)
        self.add_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def _selected_finding_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def add_finding(self) -> None:
        if self.audit_id is None:
            return

        dialog = FindingDialog(self, title="Zjištění auditu")
        if dialog.exec():
            data = dialog.get_data()
            if not data["description"]:
                QMessageBox.information(self, "Zjištění", "Vyplňte popis zjištění.")
                return
            finding_service.create(ENTITY_AUDITY, self.audit_id, **data)
            self.refresh()

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

        dialog = FindingDialog(self, finding=finding, title="Zjištění auditu")
        if dialog.exec():
            data = dialog.get_data()
            if not data["description"]:
                QMessageBox.information(self, "Zjištění", "Vyplňte popis zjištění.")
                return
            finding_service.update(finding_id, **data)
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
