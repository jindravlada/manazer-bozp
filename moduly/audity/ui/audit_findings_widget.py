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
    ENTITY_AUDITY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)
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
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.audity.constants import (
    FINDING_DIALOG_TITLE,
    FINDING_SOURCE_LABEL,
    PROCESS_TERM_CRITERION,
    PROCESS_TERM_PROCESS,
    PROCESS_TERM_QUESTION,
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


class AuditFindingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit_id: int | None = None
        self._on_task_changed = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Zjištění lze přidat až po uložení auditu.")
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
            PROCESS_TERM_PROCESS,
            PROCESS_TERM_CRITERION,
            PROCESS_TERM_QUESTION,
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
        enable_typed_sorting(self.table)

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

        self.edit_btn.clicked.connect(self.edit_finding)
        self.delete_btn.clicked.connect(self.delete_finding)
        self.table.doubleClicked.connect(self.edit_finding)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        self._update_state()
        self._update_row_actions()
        self.task_actions.update_state()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.audit_id = audit_id
        self.refresh()
        self._update_state()

    def set_on_task_changed(self, callback) -> None:
        self._on_task_changed = callback

    def refresh(self) -> None:
        findings = []
        summary = {"total": 0}

        if self.audit_id is not None:
            findings = finding_service.get_for_entity(ENTITY_AUDITY, self.audit_id)
            summary = finding_service.summarize(ENTITY_AUDITY, self.audit_id)

        self.summary_panel.update_summary(summary)
        self.summary_panel.setVisible(self.audit_id is not None)
        self.content_stack.setCurrentIndex(1 if findings else 0)
        self.empty_label.setText(
            "Audit zatím neobsahuje žádné zjištění."
            if self.audit_id is not None
            else "Zjištění lze zobrazit až po uložení auditu."
        )

        with sorting_paused(self.table):
            self.table.setRowCount(len(findings))
            for row, finding in enumerate(findings):
                record_id = int(finding.id)
                tooltip = self._finding_tooltip(finding)
                description = self._text_preview(finding.description)
                area = finding.source_area_label or "—"
                section = finding.source_section_label or "—"
                control_point = finding.source_control_point_label or "—"
                reference = finding.reference_label or "—"
                type_label = finding_type_label(finding.finding_type)
                status_label = finding_status_label(finding.status)
                cells = [
                    create_typed_item(
                        str(finding.id),
                        typed_int(finding.id),
                        stable_id=record_id,
                    ),
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
                    create_typed_item(area, _text_or_empty(area), stable_id=record_id),
                    create_typed_item(section, _text_or_empty(section), stable_id=record_id),
                    create_typed_item(
                        control_point,
                        _text_or_empty(control_point),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        reference,
                        _text_or_empty(reference),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        description,
                        typed_text(finding.description),
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
                    if column == 8:
                        item.setBackground(QBrush(QColor(finding_status_background(finding.status))))
                        item.setForeground(QBrush(QColor(finding_status_text_color(finding.status))))
                    self.table.setItem(row, column, item)

        self.task_actions.update_state()
        self._update_row_actions()

    def _after_task_action(self) -> None:
        self.refresh()
        if self._on_task_changed is not None:
            self._on_task_changed()

    def _on_selection_changed(self) -> None:
        self._update_row_actions()
        self.task_actions.update_state()

    def _update_state(self) -> None:
        self.info_label.setVisible(self.audit_id is None)
        self._update_row_actions()

    def _update_row_actions(self) -> None:
        has_row = self.audit_id is not None and self._selected_finding_id() is not None
        self.edit_btn.setEnabled(has_row)
        self.delete_btn.setEnabled(has_row)

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
                "source_label": FINDING_SOURCE_LABEL,
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
            f"{PROCESS_TERM_PROCESS}: {finding.source_area_label or '—'}",
            f"{PROCESS_TERM_CRITERION}: {finding.source_section_label or '—'}",
            f"{PROCESS_TERM_QUESTION}: {finding.source_control_point_label or '—'}",
            f"Reference: {finding.reference_label or '—'}",
            f"Popis: {finding.description or '—'}",
            f"Stav: {finding_status_label(finding.status)}",
        ]
        return "\n".join(lines)
