"""Záložka Agendy – Roční plán (celoroční pohled)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rocni_plan.constants import (
    ACTION_CANCEL,
    ACTION_CREATE_MEETING,
    ACTION_CREATE_TASK,
    ACTION_EDIT,
    ACTION_MARK_MONTH_PROCESSED,
    ACTION_MOVE,
    ACTION_NEW,
    ALREADY_LINKED_MESSAGE,
    CANCEL_CONFIRM_MESSAGE,
    CANCELLED_ACTION_MESSAGE,
    ITEM_NOT_FOUND_MESSAGE,
    MARK_MONTH_PROCESSED_CONFIRM,
    MAX_YEAR,
    MIN_YEAR,
    MONTH_ALREADY_PROCESSED_MESSAGE,
    SOURCE_MODULE_YEARLY_PLAN,
    STATUS_CANCELLED,
    STATUS_PLANNED,
    TAB_YEARLY_PLAN,
    format_processed_at,
)
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    periodic_activity_service,
)
from moduly.periodicke_cinnosti.ui.periodic_activity_dialog import PeriodicActivityDialog
from moduly.rocni_plan.sluzby.yearly_plan_service import (
    YearlyPlanValidationError,
    is_repeating,
    yearly_plan_service,
)
from moduly.rocni_plan.ui.yearly_plan_item_dialog import YearlyPlanItemDialog
from moduly.rocni_plan.ui.yearly_plan_move_dialog import YearlyPlanMoveDialog
from moduly.rocni_plan.ui.yearly_plan_table import (
    YearlyPlanMonthSection,
    YearlyPlanTable,
)
from moduly.schuzky.constants import LIST_WINDOW_TITLE as MEETINGS_TITLE
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import (
    MeetingValidationError,
    meeting_service,
)
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class YearlyPlanTab(QWidget):
    def __init__(self, parent=None, *, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._focus_month = date.today().month
        self._pending_scroll_month: int | None = None

        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Rok:"))
        self.year_combo = QComboBox()
        for year in range(MIN_YEAR, MAX_YEAR + 1):
            self.year_combo.addItem(str(year), year)
        filters.addWidget(self.year_combo)
        filters.addStretch()

        today = date.today()
        year_index = self.year_combo.findData(today.year)
        if year_index >= 0:
            self.year_combo.setCurrentIndex(year_index)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.create_task_btn = QPushButton(ACTION_CREATE_TASK)
        self.create_meeting_btn = QPushButton(ACTION_CREATE_MEETING)
        self.move_btn = QPushButton(ACTION_MOVE)
        self.cancel_btn = QPushButton(ACTION_CANCEL)
        self.mark_month_btn = QPushButton(ACTION_MARK_MONTH_PROCESSED)
        # Kompatibilita se staršími testy – stav fokusovaného měsíce.
        self.month_status_label = QLabel("")
        self.month_status_label.setObjectName("MutedText")
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("MutedText")
        self.summary_label.hide()
        for button in (
            self.edit_btn,
            self.create_task_btn,
            self.create_meeting_btn,
            self.move_btn,
            self.cancel_btn,
            self.mark_month_btn,
        ):
            button.setEnabled(False)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.create_task_btn)
        toolbar.addWidget(self.create_meeting_btn)
        toolbar.addWidget(self.move_btn)
        toolbar.addWidget(self.cancel_btn)
        toolbar.addWidget(self.mark_month_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.month_status_label)

        self.table = YearlyPlanTable()
        configure_table_columns(self.table, "yearly_plan")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat v Ročním plánu...")
        self.text_filter.search_edit.textChanged.connect(self._after_filter)

        layout.addLayout(filters)
        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary_label)

        self.new_btn.clicked.connect(self.new_item)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.create_task_btn.clicked.connect(self.create_task_for_selected)
        self.create_meeting_btn.clicked.connect(self.create_meeting_for_selected)
        self.move_btn.clicked.connect(self.move_selected)
        self.cancel_btn.clicked.connect(self.cancel_selected)
        self.mark_month_btn.clicked.connect(self.mark_month_processed)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def current_year(self) -> int:
        return int(self.year_combo.currentData())

    def current_month(self) -> int:
        """Fokusovaný měsíc (scroll / poslední set_year_month)."""
        return int(self._focus_month)

    def set_year_month(self, year: int, month: int) -> None:
        self._focus_month = int(month)
        self._pending_scroll_month = int(month)
        year_index = self.year_combo.findData(year)
        if year_index >= 0:
            if self.year_combo.currentIndex() != year_index:
                self.year_combo.setCurrentIndex(year_index)
                return  # refresh přes _on_year_changed
        self.refresh()

    def _on_year_changed(self, *_args) -> None:
        self.refresh()

    def _after_filter(self, *_args) -> None:
        text = self.text_filter.search_edit.text().strip()
        if not text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return
        self.table.ensure_month_headers_visibility()

    def refresh(self) -> None:
        year = self.current_year()
        sections: list[YearlyPlanMonthSection] = []
        focus_rows = []
        for month in range(1, 13):
            rows = yearly_plan_service.list_month_rows(year, month)
            summary = yearly_plan_service.month_summary(rows)
            status = yearly_plan_service.get_month_status(year, month)
            sections.append(
                YearlyPlanMonthSection(
                    month=month,
                    rows=rows,
                    summary=summary,
                    processed_at=status.processed_at if status is not None else None,
                )
            )
            if month == self._focus_month:
                focus_rows = rows

        self.table.load_year_sections(sections)
        configure_table_columns(self.table, "yearly_plan")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._refresh_action_buttons()
        self._refresh_focus_month_state(focus_rows)
        self._scroll_pending_month()

    def _scroll_pending_month(self) -> None:
        month = self._pending_scroll_month
        if month is None:
            return
        self._pending_scroll_month = None

        def _do_scroll() -> None:
            self.table.scroll_to_month(month)

        QTimer.singleShot(0, _do_scroll)

    def _refresh_focus_month_state(self, focus_rows) -> None:
        summary = yearly_plan_service.month_summary(focus_rows)
        self.summary_label.setText(
            "Celkem: {total}   Splněno: {done}   Řeší se: {in_progress}   "
            "Resty: {rest}   Zrušeno: {cancelled}".format(**summary)
        )
        status = yearly_plan_service.get_month_status(
            self.current_year(),
            self._focus_month,
        )
        if status is None:
            self.month_status_label.setText("")
            return
        self.month_status_label.setText(
            f"Zpracováno: {format_processed_at(status.processed_at)}"
        )

    def _month_for_mark_action(self) -> int | None:
        """Měsíc jen z označeného oddělovacího řádku (ne z položky, ne z dialogu)."""
        if not self.table.selected_is_month_header():
            return None
        return self.table.selected_header_month()

    def mark_month_processed(self) -> None:
        if not self.mark_month_btn.isEnabled():
            return
        month = self._month_for_mark_action()
        if month is None:
            return
        year = self.current_year()
        if yearly_plan_service.is_month_processed(year, month):
            QMessageBox.warning(
                self,
                ACTION_MARK_MONTH_PROCESSED,
                MONTH_ALREADY_PROCESSED_MESSAGE,
            )
            return
        answer = QMessageBox.question(
            self,
            ACTION_MARK_MONTH_PROCESSED,
            MARK_MONTH_PROCESSED_CONFIRM,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            yearly_plan_service.mark_month_processed(year, month)
        except YearlyPlanValidationError as error:
            QMessageBox.warning(self, ACTION_MARK_MONTH_PROCESSED, str(error))
            self.refresh()
            return
        self._focus_month = month
        self.refresh()
        self._notify_changed()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _selected_item(self):
        item_id = self.table.selected_item_id()
        if item_id is None:
            return None
        return yearly_plan_service.get_by_id(item_id)

    def _selected_slot(self) -> tuple[int, int] | None:
        return self.table.selected_slot_year_month()

    def _occurrence_state(self, item):
        """Vrátí (status, task_id, meeting_id) pro vybraný řádek."""
        if item is None:
            return None, None, None
        if not self.table.selected_is_recurring() and not is_repeating(item):
            return item.status, item.task_id, item.meeting_id
        slot = self._selected_slot()
        if slot is None:
            return STATUS_PLANNED, None, None
        occurrence = yearly_plan_service.get_occurrence(item.id, slot[0], slot[1])
        if occurrence is None:
            return STATUS_PLANNED, None, None
        return occurrence.status, occurrence.task_id, occurrence.meeting_id

    def _has_link_ids(self, task_id, meeting_id) -> bool:
        return task_id is not None or meeting_id is not None

    def _refresh_action_buttons(self, *_args) -> None:
        single = self._selected_row_count() == 1
        is_header = bool(single and self.table.selected_is_month_header())
        is_periodic = bool(single and self.table.selected_is_periodic())

        if is_header:
            month = self.table.selected_header_month()
            can_mark = bool(
                month is not None
                and not yearly_plan_service.is_month_processed(
                    self.current_year(),
                    month,
                )
            )
            self.mark_month_btn.setEnabled(can_mark)
        else:
            self.mark_month_btn.setEnabled(False)

        if not single or is_header or is_periodic:
            self.edit_btn.setEnabled(False)
            self.create_task_btn.setEnabled(False)
            self.create_meeting_btn.setEnabled(False)
            self.move_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            return
        item = self._selected_item()
        self.edit_btn.setEnabled(item is not None)
        status, task_id, meeting_id = self._occurrence_state(item)
        can_act = bool(item and status != STATUS_CANCELLED)
        unlinked = bool(can_act and not self._has_link_ids(task_id, meeting_id))
        self.create_task_btn.setEnabled(unlinked)
        self.create_meeting_btn.setEnabled(unlinked)
        self.move_btn.setEnabled(can_act)
        self.cancel_btn.setEnabled(can_act)

    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()
        if self._selected_row_count() != 1 and not index.isValid():
            return
        if self.table.selected_is_month_header():
            return
        menu = QMenu(self)
        for label, handler, button in (
            (ACTION_EDIT, self.edit_selected, self.edit_btn),
            (ACTION_CREATE_TASK, self.create_task_for_selected, self.create_task_btn),
            (ACTION_CREATE_MEETING, self.create_meeting_for_selected, self.create_meeting_btn),
            (ACTION_MOVE, self.move_selected, self.move_btn),
            (ACTION_CANCEL, self.cancel_selected, self.cancel_btn),
        ):
            action = menu.addAction(label, handler)
            action.setEnabled(button.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_item(self) -> None:
        today = date.today()
        default_month = today.month if today.year == self.current_year() else 1
        dialog = YearlyPlanItemDialog(
            self,
            default_year=self.current_year(),
            default_month=default_month,
        )
        exec_maximized(dialog)
        self.refresh()
        if dialog.item is not None:
            self._focus_month = int(dialog.item.month)
            self._pending_scroll_month = self._focus_month
            self._scroll_pending_month()
            self._notify_changed()

    def edit_selected(self) -> None:
        if self._selected_row_count() != 1:
            return
        if self.table.selected_is_month_header():
            return
        if self.table.selected_is_periodic():
            self._open_selected_periodic()
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = YearlyPlanItemDialog(self, item=item)
        exec_maximized(dialog)
        self.refresh()
        self._notify_changed()

    def _open_selected_periodic(self) -> None:
        activity_id = self.table.selected_activity_id()
        if activity_id is None:
            return
        activity = periodic_activity_service.get_by_id(activity_id)
        if activity is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = PeriodicActivityDialog(self, activity=activity)
        exec_maximized(dialog)
        self.refresh()
        self._notify_changed()

    def move_selected(self) -> None:
        if not self.move_btn.isEnabled():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        slot = self._selected_slot()
        from_year = self.current_year()
        from_month = self._focus_month
        if slot is not None:
            from_year, from_month = slot
        if self.table.selected_is_recurring() and slot is not None:
            occurrence = yearly_plan_service.get_occurrence(item.id, slot[0], slot[1])
            if occurrence is not None:
                from_year = occurrence.display_year
                from_month = occurrence.display_month
        dialog = YearlyPlanMoveDialog(
            self,
            from_year=from_year,
            from_month=from_month,
            default_year=from_year,
            default_month=from_month,
        )
        if not dialog.exec():
            return
        try:
            if self.table.selected_is_recurring() and slot is not None:
                yearly_plan_service.move_occurrence(
                    item.id,
                    year=slot[0],
                    month=slot[1],
                    to_year=dialog.selected_year(),
                    to_month=dialog.selected_month(),
                )
                self._focus_month = dialog.selected_month()
                if dialog.selected_year() != self.current_year():
                    self.set_year_month(dialog.selected_year(), dialog.selected_month())
                else:
                    self._pending_scroll_month = self._focus_month
                    self.refresh()
            else:
                moved = yearly_plan_service.move_to_month(
                    item.id,
                    to_year=dialog.selected_year(),
                    to_month=dialog.selected_month(),
                )
                self.set_year_month(moved.year, moved.month)
        except YearlyPlanValidationError as error:
            QMessageBox.warning(self, ACTION_MOVE, str(error))
            return
        self._notify_changed()

    def cancel_selected(self) -> None:
        if not self.cancel_btn.isEnabled():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        answer = QMessageBox.question(
            self,
            ACTION_CANCEL,
            CANCEL_CONFIRM_MESSAGE,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.table.selected_is_recurring():
                slot = self._selected_slot()
                if slot is None:
                    raise YearlyPlanValidationError(ITEM_NOT_FOUND_MESSAGE)
                yearly_plan_service.cancel_occurrence(
                    item.id,
                    year=slot[0],
                    month=slot[1],
                )
            else:
                yearly_plan_service.cancel(item.id)
        except YearlyPlanValidationError as error:
            QMessageBox.warning(self, ACTION_CANCEL, str(error))
            return
        self.refresh()
        self._notify_changed()

    def create_task_for_selected(self) -> None:
        if not self.create_task_btn.isEnabled():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        status, task_id, meeting_id = self._occurrence_state(item)
        if status == STATUS_CANCELLED:
            QMessageBox.warning(self, ACTION_CREATE_TASK, CANCELLED_ACTION_MESSAGE)
            return
        if self._has_link_ids(task_id, meeting_id):
            QMessageBox.warning(self, ACTION_CREATE_TASK, ALREADY_LINKED_MESSAGE)
            return

        dialog = TaskDialog(self)
        dialog.title_edit.setPlainText(item.title or "")
        dialog.requires_verification_checkbox.setChecked(False)
        if item.note:
            dialog.note_edit.setPlainText(item.note)
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data.get("title"):
            return
        task = task_service.create_task(
            **data,
            source_module=SOURCE_MODULE_YEARLY_PLAN,
            source_record_id=item.id,
            requires_verification=False,
        )
        try:
            if self.table.selected_is_recurring():
                slot = self._selected_slot()
                if slot is None:
                    raise YearlyPlanValidationError(ITEM_NOT_FOUND_MESSAGE)
                yearly_plan_service.link_task_occurrence(
                    item.id,
                    year=slot[0],
                    month=slot[1],
                    task_id=task.id,
                )
            else:
                yearly_plan_service.link_task(item.id, task.id)
        except YearlyPlanValidationError as error:
            QMessageBox.warning(self, ACTION_CREATE_TASK, str(error))
            return
        self.refresh()
        self._notify_changed()

    def create_meeting_for_selected(self) -> None:
        if not self.create_meeting_btn.isEnabled():
            return
        item = self._selected_item()
        if item is None:
            QMessageBox.warning(self, TAB_YEARLY_PLAN, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        status, task_id, meeting_id = self._occurrence_state(item)
        if status == STATUS_CANCELLED:
            QMessageBox.warning(self, ACTION_CREATE_MEETING, CANCELLED_ACTION_MESSAGE)
            return
        if self._has_link_ids(task_id, meeting_id):
            QMessageBox.warning(self, ACTION_CREATE_MEETING, ALREADY_LINKED_MESSAGE)
            return

        dialog = MeetingDialog(self)
        dialog.title_edit.setText(item.title or "")
        if not exec_maximized(dialog):
            return
        try:
            meeting = meeting_service.create_meeting(**dialog.get_data())
            meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
            if self.table.selected_is_recurring():
                slot = self._selected_slot()
                if slot is None:
                    raise YearlyPlanValidationError(ITEM_NOT_FOUND_MESSAGE)
                yearly_plan_service.link_meeting_occurrence(
                    item.id,
                    year=slot[0],
                    month=slot[1],
                    meeting_id=meeting.id,
                )
            else:
                yearly_plan_service.link_meeting(item.id, meeting.id)
        except (MeetingValidationError, YearlyPlanValidationError) as error:
            QMessageBox.warning(self, MEETINGS_TITLE, str(error))
            return
        self.refresh()
        self._notify_changed()

    def _notify_changed(self) -> None:
        if callable(self._on_changed):
            self._on_changed()
