"""Záložka Agendy – Státní dozor."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_edit_action_button,
    configure_new_action_button,
    exec_maximized,
)
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.statni_dozor.constants import (
    ACTION_EDIT,
    ACTION_NEW,
    EMPTY_STATE_FILTER,
    EMPTY_STATE_NONE,
    FILTER_ALL,
    FILTER_MODE_ACTIVE,
    FILTER_MODE_CLOSED,
    FILTER_MODES,
    ITEM_NOT_FOUND_MESSAGE,
    LOAD_ERROR_TEXT,
    MODULE_NAME,
    STATE_SUPERVISION_STATUS_LABELS,
    STATE_SUPERVISION_STATUS_ORDER,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_CUBE_HINT,
)
from moduly.statni_dozor.modely.state_supervision import StateSupervision
from moduly.statni_dozor.sluzby.state_supervision_attention import (
    state_supervision_attention_service,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    state_supervision_service,
)
from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
    StateSupervisionEditorDialog,
)
from moduly.statni_dozor.ui.state_supervision_table import (
    StateSupervisionTable,
    decisive_datetime,
)

logger = logging.getLogger(__name__)


class StateSupervisionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._unfiltered_count = 0
        self._load_error: str | None = None
        self._updating_filters = False

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        configure_new_action_button(self.new_btn)
        configure_edit_action_button(self.edit_btn)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Zobrazit:"))
        self.mode_filter = QComboBox()
        self.mode_filter.addItems(list(FILTER_MODES))
        self.mode_filter.setCurrentText(FILTER_ALL)
        filters.addWidget(self.mode_filter)

        filters.addWidget(QLabel("Rok:"))
        self.year_filter = QComboBox()
        filters.addWidget(self.year_filter)

        filters.addWidget(QLabel("Kontrolní orgán:"))
        self.authority_filter = QComboBox()
        filters.addWidget(self.authority_filter)

        filters.addWidget(QLabel("Provoz / pracoviště:"))
        self.workplace_filter = QComboBox()
        filters.addWidget(self.workplace_filter)

        filters.addWidget(QLabel("Stav:"))
        self.status_filter = QComboBox()
        filters.addWidget(self.status_filter)
        filters.addStretch()

        self.table = StateSupervisionTable()
        configure_table_columns(self.table, "state_supervision_overview")
        self.text_filter = FilterBar(
            self.table, placeholder="🔍 Hledat ve státním dozoru..."
        )
        self.hint_label = QLabel(STATUS_CUBE_HINT)
        self.hint_label.setStyleSheet("color: #666;")
        self.hint_label.setWordWrap(True)

        self.empty_label = QLabel(EMPTY_STATE_NONE)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addLayout(toolbar)
        layout.addLayout(filters)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_supervision)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)
        self.mode_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.year_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.authority_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.workplace_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.text_filter.search_edit.textChanged.connect(self._update_empty_state)
        self.text_filter.search_edit.textChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self, *, select_id: int | None = None) -> None:
        try:
            records = state_supervision_service.list_supervisions()
        except Exception:
            logger.exception("Načtení přehledu státního dozoru selhalo.")
            self._unfiltered_count = 0
            self._load_error = LOAD_ERROR_TEXT
            self.table.load_records([])
            self._rebuild_filter_options([])
            self.text_filter.update_count()
            self._update_empty_state()
            self._refresh_action_buttons()
            return

        self._load_error = None
        self._unfiltered_count = len(records)
        self._rebuild_filter_options(records)
        visible = self._apply_combo_filters(records)
        attentions = {}
        attention_error = False
        try:
            attentions = state_supervision_attention_service.summarize(visible)
        except Exception:
            logger.exception("Vyhodnocení upozornění státního dozoru selhalo.")
            attention_error = True
        self.table.load_records(
            visible,
            attentions=attentions,
            attention_error=attention_error,
        )
        configure_table_columns(self.table, "state_supervision_overview")
        self.text_filter.update_count()
        self._update_empty_state()
        if select_id is not None:
            self.table.select_by_id(select_id)
        else:
            self.table.clear_selection()
        self._refresh_action_buttons()

    def _on_filter_changed(self) -> None:
        if self._updating_filters:
            return
        self.refresh()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        self.edit_btn.setEnabled(self._selected_row_count() == 1)

    def new_supervision(self) -> None:
        self._open_editor(None)

    def edit_selected(self) -> None:
        if self._selected_row_count() != 1:
            return
        supervision_id = self.table.selected_supervision_id()
        if supervision_id is None:
            return
        self._open_editor(supervision_id)

    def open_supervision(self, supervision_id: int) -> None:
        """Otevře editor kontroly podle ID (i když aktuální filtr řádek skrývá)."""
        record = state_supervision_service.get_supervision(supervision_id)
        if record is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        self.table.select_by_id(supervision_id)
        self._refresh_action_buttons()
        self._open_editor(supervision_id)

    def _open_editor(self, supervision_id: int | None) -> None:
        if supervision_id is not None:
            record = state_supervision_service.get_supervision(supervision_id)
            if record is None:
                QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
                self.refresh()
                return
        dialog = StateSupervisionEditorDialog(self, supervision_id=supervision_id)
        exec_maximized(dialog)
        if dialog.saved:
            self.refresh(select_id=dialog.supervision_id)

    def _rebuild_filter_options(self, records: list[StateSupervision]) -> None:
        self._updating_filters = True
        try:
            self._fill_combo(
                self.year_filter,
                self._year_options(records),
                value_is_int=True,
            )
            self._fill_combo(
                self.authority_filter,
                sorted({str(item.authority_name or "").strip() for item in records if str(item.authority_name or "").strip()}),
            )
            self._fill_combo(
                self.workplace_filter,
                sorted(
                    {
                        str(item.workplace_name_snapshot or "").strip()
                        for item in records
                        if str(item.workplace_name_snapshot or "").strip()
                    }
                ),
            )
            self._fill_status_combo()
        finally:
            self._updating_filters = False

    def _fill_combo(
        self,
        combo: QComboBox,
        values: list[str] | list[int],
        *,
        value_is_int: bool = False,
    ) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(FILTER_ALL, None)
        for value in values:
            combo.addItem(str(value), int(value) if value_is_int else value)
        index = combo.findData(previous)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _fill_status_combo(self) -> None:
        previous = self.status_filter.currentData()
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem(FILTER_ALL, None)
        for status in STATE_SUPERVISION_STATUS_ORDER:
            self.status_filter.addItem(
                STATE_SUPERVISION_STATUS_LABELS[status],
                status,
            )
        index = self.status_filter.findData(previous)
        self.status_filter.setCurrentIndex(index if index >= 0 else 0)
        self.status_filter.blockSignals(False)

    def _year_options(self, records: list[StateSupervision]) -> list[int]:
        years: set[int] = set()
        for record in records:
            stamp = decisive_datetime(record)
            if stamp is not None:
                years.add(int(stamp.year))
        return sorted(years, reverse=True)

    def _apply_combo_filters(
        self, records: list[StateSupervision]
    ) -> list[StateSupervision]:
        mode = self.mode_filter.currentText()
        year = self.year_filter.currentData()
        authority = self.authority_filter.currentData()
        workplace = self.workplace_filter.currentData()
        status = self.status_filter.currentData()

        visible: list[StateSupervision] = []
        for record in records:
            if mode == FILTER_MODE_ACTIVE and record.status in {
                STATUS_CLOSED,
                STATUS_CANCELLED,
            }:
                continue
            if mode == FILTER_MODE_CLOSED and record.status != STATUS_CLOSED:
                continue
            if year is not None:
                stamp = decisive_datetime(record)
                if stamp is None or int(stamp.year) != int(year):
                    continue
            if authority and str(record.authority_name or "").strip() != str(authority):
                continue
            if (
                workplace
                and str(record.workplace_name_snapshot or "").strip() != str(workplace)
            ):
                continue
            if status and record.status != status:
                continue
            visible.append(record)
        return visible

    def _visible_row_count(self) -> int:
        return sum(
            1
            for row in range(self.table.rowCount())
            if not self.table.isRowHidden(row)
        )

    def _update_empty_state(self) -> None:
        if self._load_error:
            self.empty_label.setText(self._load_error)
            self.empty_label.show()
            self.table.hide()
            return
        if self._unfiltered_count == 0:
            self.empty_label.setText(EMPTY_STATE_NONE)
            self.empty_label.show()
            self.table.hide()
            return
        if self.table.rowCount() == 0 or self._visible_row_count() == 0:
            self.empty_label.setText(EMPTY_STATE_FILTER)
            self.empty_label.show()
            self.table.hide()
            return
        self.empty_label.hide()
        self.table.show()
