"""Přehled mimořádných auditních otázek (AUDIT-EXTRAORDINARY-1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_close_push_button, exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.audity.constants import (
    EXTRAORDINARY_QUESTIONS_DIALOG_TITLE,
    EXTRAORDINARY_QUESTION_STATUS_ACTIVE,
    EXTRAORDINARY_QUESTION_STATUS_CANCELLED,
    EXTRAORDINARY_QUESTION_STATUS_LABELS,
    EXTRAORDINARY_QUESTION_STATUS_COMPLETED,
)
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    AuditExtraordinaryError,
    ExtraordinaryQuestionOverviewRow,
    audit_extraordinary_question_service,
)
from moduly.audity.ui.extraordinary_question_editor_dialog import (
    ExtraordinaryQuestionEditorDialog,
)

COL_TEXT = 0
COL_SOURCE = 1
COL_DATE = 2
COL_STATUS = 3
COL_TARGETS = 4
COL_PENDING = 5
COL_ASSIGNED = 6
COL_VERIFIED = 7
COL_CANCELLED = 8

STATUS_FILTER_ALL = "Vše"
STATUS_FILTER_ACTIVE = "Aktivní"
STATUS_FILTER_COMPLETED = "Dokončené"
STATUS_FILTER_CANCELLED = "Zrušené"


class ExtraordinaryQuestionsDialog(QDialog):
    """Samostatný přehled evidence mimořádných otázek."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(EXTRAORDINARY_QUESTIONS_DIALOG_TITLE)
        self.resize(980, 560)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Jednorázové mimořádné otázky čekají na nejbližší budoucí audit "
            "cílových provozů. V této fázi se pouze evidují — do auditu se "
            "zatím nepřiřazují."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová otázka")
        self.edit_btn = QPushButton("Upravit")
        self.open_btn = QPushButton("Otevřít")
        self.cancel_btn = QPushButton("Zrušit")
        self.reactivate_btn = QPushButton("Obnovit")
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            [
                STATUS_FILTER_ALL,
                STATUS_FILTER_ACTIVE,
                STATUS_FILTER_COMPLETED,
                STATUS_FILTER_CANCELLED,
            ]
        )
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.cancel_btn)
        toolbar.addWidget(self.reactivate_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "Otázka",
                "Zadal / zdroj",
                "Datum",
                "Stav",
                "Cíle",
                "Čeká",
                "Přiřazeno",
                "Ověřeno",
                "Zrušeno",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.doubleClicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self._refresh_actions)

        self.text_filter = FilterBar(self.table)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_btn = QPushButton()
        configure_close_push_button(self.close_btn)
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

        self.new_btn.clicked.connect(self.new_question)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.open_btn.clicked.connect(self.open_selected)
        self.cancel_btn.clicked.connect(self.cancel_selected)
        self.reactivate_btn.clicked.connect(self.reactivate_selected)
        self.status_filter.currentIndexChanged.connect(self.refresh)

        self._single_buttons = (
            self.edit_btn,
            self.open_btn,
            self.cancel_btn,
            self.reactivate_btn,
        )
        self.refresh()

    def refresh(self) -> None:
        rows = self._filtered_rows(
            audit_extraordinary_question_service.list_overview_rows()
        )
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [
                row.question_text,
                row.assigned_by,
                row.assigned_on.isoformat() if row.assigned_on else "",
                EXTRAORDINARY_QUESTION_STATUS_LABELS.get(row.status, row.status),
                str(row.targets_total),
                str(row.pending_count),
                str(row.assigned_count),
                str(row.verified_count),
                str(row.cancelled_count),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == COL_TEXT:
                    item.setData(Qt.ItemDataRole.UserRole, row.question_id)
                self.table.setItem(index, col, item)
        self.table.resizeColumnsToContents()
        self.text_filter.apply_filter()
        self._refresh_actions()

    def _filtered_rows(
        self,
        rows: list[ExtraordinaryQuestionOverviewRow],
    ) -> list[ExtraordinaryQuestionOverviewRow]:
        mode = self.status_filter.currentText()
        if mode == STATUS_FILTER_ACTIVE:
            return [row for row in rows if row.status == EXTRAORDINARY_QUESTION_STATUS_ACTIVE]
        if mode == STATUS_FILTER_COMPLETED:
            return [
                row for row in rows if row.status == EXTRAORDINARY_QUESTION_STATUS_COMPLETED
            ]
        if mode == STATUS_FILTER_CANCELLED:
            return [
                row for row in rows if row.status == EXTRAORDINARY_QUESTION_STATUS_CANCELLED
            ]
        return list(rows)

    def _selected_question_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), COL_TEXT)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _selected_row(self) -> ExtraordinaryQuestionOverviewRow | None:
        question_id = self._selected_question_id()
        if question_id is None:
            return None
        for row in audit_extraordinary_question_service.list_overview_rows():
            if row.question_id == question_id:
                return row
        return None

    def _refresh_actions(self) -> None:
        single = self._selected_question_id() is not None
        row = self._selected_row() if single else None
        self.edit_btn.setEnabled(single)
        self.open_btn.setEnabled(single)
        self.cancel_btn.setEnabled(
            single and row is not None and row.status == EXTRAORDINARY_QUESTION_STATUS_ACTIVE
        )
        self.reactivate_btn.setEnabled(
            single
            and row is not None
            and row.status == EXTRAORDINARY_QUESTION_STATUS_CANCELLED
        )

    def new_question(self) -> None:
        dialog = ExtraordinaryQuestionEditorDialog(self)
        exec_maximized(dialog)
        self.refresh()

    def edit_selected(self) -> None:
        question_id = self._selected_question_id()
        if question_id is None:
            return
        dialog = ExtraordinaryQuestionEditorDialog(self, question_id=question_id)
        exec_maximized(dialog)
        self.refresh()

    def open_selected(self) -> None:
        self.edit_selected()

    def cancel_selected(self) -> None:
        question_id = self._selected_question_id()
        if question_id is None:
            return
        answer = QMessageBox.question(
            self,
            EXTRAORDINARY_QUESTIONS_DIALOG_TITLE,
            "Zrušit vybranou mimořádnou otázku? Záznam zůstane v evidenci.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            audit_extraordinary_question_service.cancel_question(question_id)
        except AuditExtraordinaryError as exc:
            QMessageBox.warning(self, EXTRAORDINARY_QUESTIONS_DIALOG_TITLE, str(exc))
        self.refresh()

    def reactivate_selected(self) -> None:
        question_id = self._selected_question_id()
        if question_id is None:
            return
        try:
            audit_extraordinary_question_service.reactivate_question(question_id)
        except AuditExtraordinaryError as exc:
            QMessageBox.warning(self, EXTRAORDINARY_QUESTIONS_DIALOG_TITLE, str(exc))
        self.refresh()
