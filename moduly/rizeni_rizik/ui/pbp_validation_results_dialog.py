"""UX-PBP-VALIDATION-1a: výsledkový dialog kontroly pravidel bezpečné práce."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
from moduly.rizeni_rizik.sluzby.pbp_validation_approval_service import (
    pbp_validation_approval_service,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
    UNSUITABLE_EMPLOYEE_RULE_REASON,
    normalize_rule_text,
    pravidla_bezpecne_prace_service,
    unsuitable_employee_rule_reason,
)

DIALOG_TITLE = "Kontrola pravidel bezpečné práce"
ALL_OK_MESSAGE = "Všechna nalezená pravidla byla zpracována."
UNSAVED_PROMPT = "Máte neuložené změny.\nChcete je zahodit?"
APPROVE_UNSAVED_PROMPT = (
    "V editoru je neuložená změna.\n"
    "Chcete ji zahodit a ponechat původní formulaci?"
)

COL_STATUS = 0
COL_AREA = 1
COL_REASON = 2
COL_ORIGINAL = 3
COLUMN_HEADERS = ("Stav", "Oblast / událost", "Důvod", "Původní formulace")

STATUS_UNSUITABLE = "Nevhodné"
STATUS_EDITED = "Upraveno"
STATUS_APPROVED = "Schváleno uživatelem"

# UserRole: stabilní identifikátor opatření (ne vizuální index řádku).
ROLE_MEASURE_ID = Qt.ItemDataRole.UserRole
ROLE_DOCUMENT_ORDER = Qt.ItemDataRole.UserRole + 1


class _IssueRow:
    """Jedna problematická formulace s vazbou na opatření."""

    def __init__(self, rule: PravidloBezpecnePrace, *, user_approved: bool = False):
        self.rule = rule
        self.original_text = rule.text
        self.draft_text = rule.text
        self.area_label = _resolve_area_label(rule)
        self.reason = (
            unsuitable_employee_rule_reason(rule.text) or UNSUITABLE_EMPLOYEE_RULE_REASON
        )
        self.user_approved = user_approved
        self.document_order = 0

    @property
    def measure_id(self) -> int:
        return int(self.rule.measure_id)

    @property
    def is_dirty(self) -> bool:
        return normalize_rule_text(self.draft_text) != normalize_rule_text(
            self.original_text
        )

    @property
    def status_label(self) -> str:
        if self.user_approved:
            return STATUS_APPROVED
        return STATUS_EDITED if self.is_dirty else STATUS_UNSUITABLE


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
    """Výsledky kontroly PBP – oprava / schválení nevhodných formulací."""

    def __init__(
        self,
        parent=None,
        *,
        warnings: list[PravidloBezpecnePrace],
        regenerate_warnings: Callable[..., list[PravidloBezpecnePrace]] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.resize(900, 640)
        self._regenerate_warnings = regenerate_warnings
        self._rows: list[_IssueRow] = []
        self._rows_by_measure: dict[int, _IssueRow] = {}
        self._current_measure_id: int | None = None
        self._loading_detail = False
        self._closing_confirmed = False
        self._suppress_empty_message = False
        self._default_sort_active = True

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Byla nalezena opatření, která nejsou formulována jako pravidla "
            "bezpečné práce pro zaměstnance. Upravte znění, nebo formulaci "
            "vědomě označte jako v pořádku."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.show_approved_cb = QCheckBox("Zobrazit uživatelsky schválené formulace")
        self.show_approved_cb.toggled.connect(self._on_show_approved_toggled)
        layout.addWidget(self.show_approved_cb)

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
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(
            self._on_sort_indicator_changed
        )
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

        action_row = QHBoxLayout()
        self.apply_btn = QPushButton("Použít změnu")
        self.approve_btn = QPushButton("Označit jako v pořádku")
        self.revoke_btn = QPushButton("Zrušit schválení")
        self.apply_btn.clicked.connect(self.apply_change)
        self.approve_btn.clicked.connect(self.approve_as_ok)
        self.revoke_btn.clicked.connect(self.revoke_approval)
        action_row.addWidget(self.apply_btn)
        action_row.addWidget(self.approve_btn)
        action_row.addWidget(self.revoke_btn)
        action_row.addStretch(1)
        detail_layout.addLayout(action_row)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        bottom = QHBoxLayout()
        self.recheck_btn = QPushButton("Znovu zkontrolovat")
        self.close_btn = QPushButton("Zavřít")
        self.recheck_btn.clicked.connect(self.recheck_all)
        self.close_btn.clicked.connect(self._request_close)
        bottom.addWidget(self.recheck_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.apply_change)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.apply_change)
        QShortcut(
            QKeySequence("Ctrl+Shift+Return"),
            self,
            activated=self.approve_as_ok,
        )
        QShortcut(
            QKeySequence("Ctrl+Shift+Enter"),
            self,
            activated=self.approve_as_ok,
        )

        self._set_rows_from_warnings(warnings)
        self._reload_table(
            select_measure_id=self._rows[0].measure_id if self._rows else None
        )
        self._update_action_buttons()
        if not self._rows:
            self._show_all_processed_if_needed()

    @property
    def issue_count(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> list[_IssueRow]:
        return list(self._rows)

    def current_row(self) -> _IssueRow | None:
        if self._current_measure_id is None:
            return None
        return self._rows_by_measure.get(self._current_measure_id)

    def has_unsaved_changes(self) -> bool:
        return any(row.is_dirty for row in self._rows)

    def apply_change(self) -> bool:
        row = self.current_row()
        if row is None or row.user_approved:
            return False
        draft = self.new_edit.toPlainText()
        visual_index = self._visual_row_for_measure(row.measure_id)
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
            self._reload_table(select_measure_id=row.measure_id)
            QMessageBox.information(
                self,
                DIALOG_TITLE,
                "Změna byla uložena, formulace však stále nevyhovuje kontrole.",
            )
            self._focus_new_text()
            return True

        self._remove_row(row.measure_id)
        next_id = self._next_measure_after_removal(visual_index)
        self._reload_table(select_measure_id=next_id)
        self._update_action_buttons()
        if next_id is not None:
            self._focus_new_text()
        else:
            self._show_all_processed_if_needed()
        return True

    def approve_as_ok(self) -> bool:
        row = self.current_row()
        if row is None or row.user_approved:
            return False
        if row.is_dirty:
            answer = QMessageBox.question(
                self,
                DIALOG_TITLE,
                APPROVE_UNSAVED_PROMPT,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            row.draft_text = row.original_text
            self._loading_detail = True
            self.new_edit.setPlainText(row.original_text)
            self._loading_detail = False

        visual_index = self._visual_row_for_measure(row.measure_id)
        pbp_validation_approval_service.approve_rule(row.rule)

        if self.show_approved_cb.isChecked():
            row.user_approved = True
            row.draft_text = row.original_text
            self._reload_table(select_measure_id=row.measure_id)
            self._update_action_buttons()
            return True

        self._remove_row(row.measure_id)
        next_id = self._next_measure_after_removal(visual_index)
        self._reload_table(select_measure_id=next_id)
        self._update_action_buttons()
        if next_id is not None:
            self._focus_new_text()
        else:
            self._show_all_processed_if_needed()
        return True

    def revoke_approval(self) -> bool:
        row = self.current_row()
        if row is None or not row.user_approved:
            return False
        pbp_validation_approval_service.revoke_rule(row.rule)
        row.user_approved = False
        if not self.show_approved_cb.isChecked():
            # Po zrušení zůstává mezi problémy (stále nevhodné).
            pass
        self._reload_table(select_measure_id=row.measure_id)
        self._update_action_buttons()
        self._focus_new_text()
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
        warnings = self._call_regenerate()
        self._set_rows_from_warnings(warnings)
        self._reload_table(
            select_measure_id=self._rows[0].measure_id if self._rows else None
        )
        self._update_action_buttons()
        if not self._rows:
            self._show_all_processed_if_needed()

    def _call_regenerate(self) -> list[PravidloBezpecnePrace]:
        assert self._regenerate_warnings is not None
        try:
            return self._regenerate_warnings(
                include_approved=self.show_approved_cb.isChecked()
            )
        except TypeError:
            return self._regenerate_warnings()

    def _on_show_approved_toggled(self, _checked: bool) -> None:
        if self._regenerate_warnings is None:
            # Bez regenerace jen skryjeme / zobrazíme lokálně nelze – ponecháme.
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
                self.show_approved_cb.blockSignals(True)
                self.show_approved_cb.setChecked(not self.show_approved_cb.isChecked())
                self.show_approved_cb.blockSignals(False)
                return
        self._suppress_empty_message = True
        warnings = self._call_regenerate()
        self._set_rows_from_warnings(warnings)
        self._reload_table(
            select_measure_id=self._rows[0].measure_id if self._rows else None
        )
        self._update_action_buttons()
        self._suppress_empty_message = False

    def _set_rows_from_warnings(self, warnings: list[PravidloBezpecnePrace]) -> None:
        self._rows = []
        self._rows_by_measure = {}
        for order, rule in enumerate(warnings):
            approved = pbp_validation_approval_service.is_rule_approved(rule)
            row = _IssueRow(rule, user_approved=approved)
            row.document_order = order
            self._rows.append(row)
            self._rows_by_measure[row.measure_id] = row

    def _remove_row(self, measure_id: int) -> None:
        self._rows = [row for row in self._rows if row.measure_id != measure_id]
        self._rows_by_measure.pop(measure_id, None)
        if self._current_measure_id == measure_id:
            self._current_measure_id = None

    def _visual_row_for_measure(self, measure_id: int) -> int:
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, COL_STATUS)
            if item is not None and int(item.data(ROLE_MEASURE_ID)) == measure_id:
                return row_index
        return 0

    def _next_measure_after_removal(self, visual_index: int) -> int | None:
        if not self._rows:
            return None
        # Po odstranění aktuálního řádku: stejný vizuální index, jinak poslední.
        # Tabulka se teprve znovu naplní – vybíráme podle aktuálního pořadí _rows
        # vzhledem k poslednímu řazení. Po reloadu aplikujeme výběr přes measure_id.
        # Nejdřív sestavíme pořadí measure_id podle aktuální tabulky bez odstraněného.
        remaining_order: list[int] = []
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, COL_STATUS)
            if item is None:
                continue
            mid = int(item.data(ROLE_MEASURE_ID))
            if mid in self._rows_by_measure:
                remaining_order.append(mid)
        if not remaining_order:
            # Tabulka ještě obsahuje starý stav – použij document / list order.
            remaining_order = [row.measure_id for row in self._rows]
        if not remaining_order:
            return None
        if visual_index < len(remaining_order):
            return remaining_order[visual_index]
        return remaining_order[-1]

    def _show_all_processed_if_needed(self) -> None:
        if self._suppress_empty_message or self._rows:
            return
        QMessageBox.information(self, DIALOG_TITLE, ALL_OK_MESSAGE)

    def _update_action_buttons(self) -> None:
        row = self.current_row()
        has_row = row is not None
        approved = bool(row and row.user_approved)
        self.apply_btn.setEnabled(has_row and not approved)
        self.approve_btn.setEnabled(has_row and not approved)
        self.revoke_btn.setEnabled(has_row and approved)
        self.new_edit.setEnabled(has_row and not approved)
        if not has_row:
            self.original_edit.clear()
            self.new_edit.clear()

    def _on_sort_indicator_changed(self, _logical: int, _order) -> None:
        self._default_sort_active = False

    def _reload_table(self, *, select_measure_id: int | None) -> None:
        sorting_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
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
                item.setData(ROLE_MEASURE_ID, row.measure_id)
                item.setData(ROLE_DOCUMENT_ORDER, row.document_order)
                if column == COL_STATUS:
                    # Stabilní řazení podle document order při „výchozím“ stavu.
                    item.setData(Qt.ItemDataRole.InitialSortOrderRole, row.document_order)
                self.table.setItem(index, column, item)
        self.table.blockSignals(False)

        if self._default_sort_active:
            # Zachovat pořadí dokumentu (pořadí naplnění).
            self.table.horizontalHeader().setSortIndicator(
                -1, Qt.SortOrder.AscendingOrder
            )
        self.table.setSortingEnabled(sorting_enabled)

        if select_measure_id is None or not self._rows:
            self.table.clearSelection()
            self._current_measure_id = None
            self._loading_detail = True
            self.original_edit.clear()
            self.new_edit.clear()
            self._loading_detail = False
            self._update_action_buttons()
            return

        self._select_measure(select_measure_id)

    def _select_measure(self, measure_id: int) -> None:
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, COL_STATUS)
            if item is not None and int(item.data(ROLE_MEASURE_ID)) == measure_id:
                self.table.selectRow(row_index)
                self._load_detail(measure_id)
                return
        # Fallback: první dostupný.
        if self._rows:
            first = self._rows[0].measure_id
            self.table.selectRow(0)
            self._load_detail(first)

    def _on_selection_changed(self) -> None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            self._current_measure_id = None
            self._update_action_buttons()
            return
        item = self.table.item(selected[0].row(), COL_STATUS)
        if item is None:
            return
        measure_id = int(item.data(ROLE_MEASURE_ID))
        self._load_detail(measure_id)

    def _load_detail(self, measure_id: int) -> None:
        row = self._rows_by_measure.get(measure_id)
        if row is None:
            return
        self._current_measure_id = measure_id
        self._loading_detail = True
        self.original_edit.setPlainText(row.original_text)
        self.new_edit.setPlainText(row.draft_text)
        self._loading_detail = False
        self._update_action_buttons()

    def _on_new_text_changed(self) -> None:
        if self._loading_detail:
            return
        row = self.current_row()
        if row is None or row.user_approved:
            return
        row.draft_text = self.new_edit.toPlainText()
        visual = self._visual_row_for_measure(row.measure_id)
        status_item = self.table.item(visual, COL_STATUS)
        if status_item is not None:
            status_item.setText(row.status_label)

    def _focus_new_text(self, *_args) -> None:
        if not self.new_edit.isEnabled():
            return
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
