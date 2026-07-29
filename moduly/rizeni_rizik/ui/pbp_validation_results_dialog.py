"""UX-PBP-VALIDATION-1: výsledkový dialog kontroly pravidel bezpečné práce."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
    UNSUITABLE_EMPLOYEE_RULE_REASON,
    normalize_rule_text,
    pravidla_bezpecne_prace_service,
    unsuitable_employee_rule_reason,
)

DIALOG_TITLE = "Kontrola pravidel bezpečné práce"
ALL_OK_MESSAGE = "Všechna pravidla jsou nyní formulována správně."
UNSAVED_PROMPT = "Máte neuložené změny.\nChcete je zahodit?"

COL_STATUS = 0
COL_AREA = 1
COL_REASON = 2
COL_ORIGINAL = 3
COLUMN_HEADERS = ("Stav", "Oblast / událost", "Důvod", "Původní formulace")

STATUS_TO_FIX = "K opravě"
STATUS_EDITED = "Upraveno"


class _IssueRow:
    """Jedna problematická formulace s vazbou na opatření."""

    def __init__(self, rule: PravidloBezpecnePrace):
        self.rule = rule
        self.original_text = rule.text
        self.draft_text = rule.text
        self.area_label = _resolve_area_label(rule)
        self.reason = unsuitable_employee_rule_reason(rule.text) or UNSUITABLE_EMPLOYEE_RULE_REASON

    @property
    def is_dirty(self) -> bool:
        return normalize_rule_text(self.draft_text) != normalize_rule_text(
            self.original_text
        )

    @property
    def status_label(self) -> str:
        return STATUS_EDITED if self.is_dirty else STATUS_TO_FIX


def _resolve_area_label(rule: PravidloBezpecnePrace) -> str:
    event_id = rule.source_event_id
    if event_id is None and rule.sources:
        event_id = rule.sources[0].source_event_id
    if event_id is not None:
        event = hazard_event_service.get_by_id(event_id)
        if event is not None and (event.name or "").strip():
            return event.name.strip()
    return "—"


class PbpValidationResultsDialog(QDialog):
    """Výsledky kontroly PBP – oprava nevhodných formulací bez QMessageBox."""

    def __init__(
        self,
        parent=None,
        *,
        warnings: list[PravidloBezpecnePrace],
        regenerate_warnings: Callable[[], list[PravidloBezpecnePrace]] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.resize(900, 640)
        self._regenerate_warnings = regenerate_warnings
        self._rows: list[_IssueRow] = [_IssueRow(rule) for rule in warnings]
        self._current_index: int | None = None
        self._loading_detail = False
        self._closing_confirmed = False

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Byla nalezena opatření, která nejsou formulována jako pravidla "
            "bezpečné práce pro zaměstnance. Upravte znění a použijte změnu."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(COLUMN_HEADERS))
        self.table.setHorizontalHeaderLabels(list(COLUMN_HEADERS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._focus_new_text)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_host)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.addWidget(QLabel("Původní formulace:"))
        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setMaximumHeight(110)
        detail_layout.addWidget(self.original_edit)
        detail_layout.addWidget(QLabel("Nové znění:"))
        self.new_edit = QTextEdit()
        self.new_edit.setMaximumHeight(140)
        self.new_edit.textChanged.connect(self._on_new_text_changed)
        detail_layout.addWidget(self.new_edit)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        buttons = QHBoxLayout()
        self.apply_btn = QPushButton("Použít změnu")
        self.recheck_btn = QPushButton("Znovu zkontrolovat")
        self.close_btn = QPushButton("Zavřít")
        self.apply_btn.clicked.connect(self.apply_change)
        self.recheck_btn.clicked.connect(self.recheck_all)
        self.close_btn.clicked.connect(self._request_close)
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(self.recheck_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_change)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.apply_change)

        self._reload_table(select_index=0 if self._rows else None)
        self._update_empty_state()

    @property
    def issue_count(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> list[_IssueRow]:
        return list(self._rows)

    def current_row(self) -> _IssueRow | None:
        if self._current_index is None:
            return None
        if not (0 <= self._current_index < len(self._rows)):
            return None
        return self._rows[self._current_index]

    def has_unsaved_changes(self) -> bool:
        return any(row.is_dirty for row in self._rows)

    def apply_change(self) -> bool:
        row = self.current_row()
        if row is None:
            return False
        draft = self.new_edit.toPlainText()
        try:
            updated = pravidla_bezpecne_prace_service.apply_rule_text(row.rule, draft)
        except ValueError as error:
            QMessageBox.warning(self, DIALOG_TITLE, str(error))
            return False

        if updated.unsuitable_for_employee:
            row.rule = updated
            row.original_text = updated.text
            row.draft_text = updated.text
            row.reason = (
                unsuitable_employee_rule_reason(updated.text)
                or UNSUITABLE_EMPLOYEE_RULE_REASON
            )
            self._reload_table(select_index=self._current_index)
            QMessageBox.information(
                self,
                DIALOG_TITLE,
                "Změna byla uložena, formulace však stále nevyhovuje kontrole.",
            )
            return True

        remove_index = self._current_index
        assert remove_index is not None
        del self._rows[remove_index]
        next_index = min(remove_index, len(self._rows) - 1) if self._rows else None
        self._reload_table(select_index=next_index)
        self._update_empty_state()
        return True

    def recheck_all(self) -> None:
        if self._regenerate_warnings is None:
            QMessageBox.warning(
                self,
                DIALOG_TITLE,
                "Opakovanou kontrolu nelze v tomto kontextu spustit.",
            )
            return
        if self.has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                DIALOG_TITLE,
                UNSAVED_PROMPT,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        warnings = self._regenerate_warnings()
        self._rows = [_IssueRow(rule) for rule in warnings]
        self._reload_table(select_index=0 if self._rows else None)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        if self._rows:
            self.apply_btn.setEnabled(True)
            self.new_edit.setEnabled(True)
            return
        self.apply_btn.setEnabled(False)
        self.new_edit.setEnabled(False)
        self.original_edit.clear()
        self.new_edit.clear()
        QMessageBox.information(self, DIALOG_TITLE, ALL_OK_MESSAGE)

    def _reload_table(self, *, select_index: int | None) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            values = (
                row.status_label,
                row.area_label,
                row.reason,
                row.original_text.replace("\n", " "),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.table.setItem(index, column, item)
        self.table.blockSignals(False)

        if select_index is None or not self._rows:
            self.table.clearSelection()
            self._current_index = None
            self._loading_detail = True
            self.original_edit.clear()
            self.new_edit.clear()
            self._loading_detail = False
            return

        select_index = max(0, min(select_index, len(self._rows) - 1))
        self.table.selectRow(select_index)
        self._load_detail(select_index)

    def _on_selection_changed(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            self._current_index = None
            return
        self._load_detail(selected[0].row())

    def _load_detail(self, index: int) -> None:
        if not (0 <= index < len(self._rows)):
            return
        self._current_index = index
        row = self._rows[index]
        self._loading_detail = True
        self.original_edit.setPlainText(row.original_text)
        self.new_edit.setPlainText(row.draft_text)
        self._loading_detail = False

    def _on_new_text_changed(self) -> None:
        if self._loading_detail:
            return
        row = self.current_row()
        if row is None:
            return
        row.draft_text = self.new_edit.toPlainText()
        status_item = self.table.item(self._current_index, COL_STATUS)
        if status_item is not None:
            status_item.setText(row.status_label)

    def _focus_new_text(self, *_args) -> None:
        self.new_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        cursor = self.new_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.new_edit.setTextCursor(cursor)

    def _request_close(self) -> None:
        if self._confirm_discard_if_needed():
            self._closing_confirmed = True
            self.accept()

    def _confirm_discard_if_needed(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        answer = QMessageBox.question(
            self,
            DIALOG_TITLE,
            UNSAVED_PROMPT,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def reject(self) -> None:
        if self._closing_confirmed or self._confirm_discard_if_needed():
            self._closing_confirmed = True
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing_confirmed or self._confirm_discard_if_needed():
            self._closing_confirmed = True
            event.accept()
            super().closeEvent(event)
            return
        event.ignore()
