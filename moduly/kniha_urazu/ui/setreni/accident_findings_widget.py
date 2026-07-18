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
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import (
    ACCIDENT_FINDING_TYPES,
    ENTITY_ACCIDENT,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    FINDING_TYPE_BEZPROSTREDNI_PRICINA,
)
from core.widgets.info_tooltip import wrap_tooltip_text
from core.shared.finding_display import (
    FINDING_TYPE_LABELS,
    finding_status_background,
    finding_status_label,
    finding_status_text_color,
    finding_type_label,
)
from core.shared.sluzby.finding_service import finding_service
from core.widgets.finding_dialog import FindingDialog
from core.widgets.finding_summary_panel import FindingSummaryPanel
from core.widgets.finding_task_actions import FindingTaskActions
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)

_FINDING_STATUS_ORDER = (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)
_FINDING_TYPE_ORDER = tuple(FINDING_TYPE_LABELS.keys())


def _order_status(value: str, order: tuple[str, ...]):
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class AccidentFindingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.accident_id: int | None = None

        layout = QVBoxLayout(self)

        self.summary_panel = FindingSummaryPanel()

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        toolbar.addWidget(self.add_btn)
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
        for column in (1, 2, 3, 5, 6, 7):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        enable_typed_sorting(self.table)

        self.content_stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        self.empty_label = QLabel("Šetření zatím neobsahuje žádné zjištění.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.empty_label)
        empty_layout.addStretch()

        self.table_page = QWidget()
        table_layout = QVBoxLayout(self.table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)

        self.content_stack.addWidget(self.empty_page)
        self.content_stack.addWidget(self.table_page)

        layout.addWidget(self.summary_panel)
        layout.addLayout(toolbar)
        layout.addWidget(self.content_stack, 1)

        self.add_btn.clicked.connect(self.add_finding)
        self.edit_btn.clicked.connect(self.edit_finding)
        self.delete_btn.clicked.connect(self.delete_finding)
        self.table.doubleClicked.connect(self.edit_finding)
        self.table.itemSelectionChanged.connect(self.task_actions.update_state)

        self._update_state()
        self.task_actions.update_state()

    def set_accident_id(self, accident_id: int | None) -> None:
        self.accident_id = accident_id
        self.refresh()
        self._update_state()

    def refresh(self) -> None:
        findings = []
        summary = {"total": 0}

        if self.accident_id is not None:
            findings = finding_service.get_for_entity(ENTITY_ACCIDENT, self.accident_id)
            summary = finding_service.summarize(ENTITY_ACCIDENT, self.accident_id)

        self.summary_panel.update_summary(summary)
        self.summary_panel.setVisible(self.accident_id is not None)

        if self.accident_id is not None and not findings:
            self.content_stack.setCurrentWidget(self.empty_page)
        else:
            self.content_stack.setCurrentWidget(self.table_page)

        with sorting_paused(self.table):
            self.table.setRowCount(len(findings))
            for row, finding in enumerate(findings):
                record_id = int(finding.id)
                tooltip = self._finding_tooltip(finding)
                reference = finding.reference_label or "—"
                description = self._text_preview(finding.description)
                responsible = finding.responsible_person_name or "—"
                due_display = (
                    "" if finding.due_date is None else finding.due_date.strftime("%d.%m.%Y")
                )
                type_label = finding_type_label(finding.finding_type)
                status_label = finding_status_label(finding.status)
                cells = [
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                    create_typed_item(
                        str(finding.display_order),
                        typed_int(finding.display_order),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        type_label,
                        _order_status(finding.finding_type, _FINDING_TYPE_ORDER),
                        stable_id=record_id,
                    ),
                    create_typed_item(reference, _text_or_empty(reference), stable_id=record_id),
                    create_typed_item(
                        description,
                        typed_text(finding.description),
                        stable_id=record_id,
                    ),
                    create_typed_item(responsible, _text_or_empty(responsible), stable_id=record_id),
                    create_typed_item(
                        due_display,
                        typed_date(finding.due_date) if finding.due_date is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status_label,
                        _order_status(finding.status, _FINDING_STATUS_ORDER),
                        stable_id=record_id,
                    ),
                ]
                for column, item in enumerate(cells):
                    item.setToolTip(tooltip)
                    if column == 7:
                        item.setBackground(QBrush(QColor(finding_status_background(finding.status))))
                        item.setForeground(QBrush(QColor(finding_status_text_color(finding.status))))
                    self.table.setItem(row, column, item)

        self.task_actions.update_state()

    def _after_task_action(self) -> None:
        self.refresh()

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
        return wrap_tooltip_text("\n".join(lines))

    def _update_state(self) -> None:
        enabled = self.accident_id is not None
        self.add_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def _selected_finding_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _finding_dialog(self, finding=None) -> FindingDialog:
        return FindingDialog(
            self,
            finding=finding,
            title="Zjištění šetření",
            allowed_finding_types=ACCIDENT_FINDING_TYPES,
            default_finding_type=FINDING_TYPE_BEZPROSTREDNI_PRICINA,
        )

    def add_finding(self) -> None:
        if self.accident_id is None:
            return

        dialog = self._finding_dialog()
        if dialog.exec():
            data = dialog.get_data()
            if not data["description"]:
                QMessageBox.information(self, "Zjištění", "Vyplňte popis zjištění.")
                return
            finding_service.create(ENTITY_ACCIDENT, self.accident_id, **data)
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

        dialog = self._finding_dialog(finding=finding)
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
