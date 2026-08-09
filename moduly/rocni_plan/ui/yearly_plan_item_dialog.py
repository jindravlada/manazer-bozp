"""Editor položky Ročního plánu."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_text,
)
from moduly.rocni_plan.constants import (
    DEFAULT_DUE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
    DEFAULT_STATUS,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    DUE_KIND_DAY,
    DUE_KIND_FIRST_WORKING_DAY,
    DUE_KIND_LABELS,
    DUE_KIND_NONE,
    MAX_YEAR,
    MIN_YEAR,
    MONTH_NAMES,
    MOVE_HISTORY_HEADERS,
    REPEAT_UNIT_LABELS,
    REPEAT_UNIT_MONTHS,
    REPEAT_UNIT_NONE,
    REPEAT_UNIT_YEARS,
    TAB_ITEM,
    TAB_MOVE_HISTORY,
    TITLE_REQUIRED_MESSAGE,
    format_year_month,
)
from moduly.rocni_plan.sluzby.yearly_plan_service import (
    YearlyPlanValidationError,
    yearly_plan_service,
)


class YearlyPlanItemDialog(QDialog):
    def __init__(
        self,
        parent=None,
        item=None,
        *,
        default_year: int | None = None,
        default_month: int | None = None,
    ):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(DIALOG_TITLE_EDIT if item is not None else DIALOG_TITLE_NEW)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=560, height=560, min_width=420, min_height=400)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._item_tab()), TAB_ITEM)
        self.tabs.addTab(wrap_in_scroll_area(self._history_tab()), TAB_MOVE_HISTORY)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=item is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=item is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        if item is not None:
            self._load_item(item)
            self._load_history(item.id)
        else:
            year = default_year or datetime.now().year
            month = default_month or datetime.now().month
            year_index = self.year_combo.findData(year)
            if year_index >= 0:
                self.year_combo.setCurrentIndex(year_index)
            month_index = self.month_combo.findData(month)
            if month_index >= 0:
                self.month_combo.setCurrentIndex(month_index)
            self._load_history(None)

        self._sync_repeat_controls()
        self._sync_due_controls()
        self._editor.capture_baseline()

    def _item_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.title_edit = QLineEdit()
        self.note_edit = QTextEdit()
        self.note_edit.setAcceptRichText(False)
        self.note_edit.setMinimumHeight(90)

        self.year_combo = QComboBox()
        for year in range(MIN_YEAR, MAX_YEAR + 1):
            self.year_combo.addItem(str(year), year)
        self.month_combo = QComboBox()
        for index, name in enumerate(MONTH_NAMES, start=1):
            self.month_combo.addItem(name, index)

        self.repeat_enabled = QComboBox()
        self.repeat_enabled.addItem("Neopakovat", REPEAT_UNIT_NONE)
        self.repeat_enabled.addItem("Každých N měsíců", REPEAT_UNIT_MONTHS)
        self.repeat_enabled.addItem("Každých N let", REPEAT_UNIT_YEARS)
        self.repeat_enabled.currentIndexChanged.connect(self._sync_repeat_controls)

        repeat_row = QWidget()
        repeat_layout = QHBoxLayout(repeat_row)
        repeat_layout.setContentsMargins(0, 0, 0, 0)
        self.repeat_every_spin = QSpinBox()
        self.repeat_every_spin.setRange(1, 120)
        self.repeat_every_spin.setValue(1)
        self.repeat_unit_label = QLabel(REPEAT_UNIT_LABELS[REPEAT_UNIT_MONTHS])
        repeat_layout.addWidget(QLabel("každých"))
        repeat_layout.addWidget(self.repeat_every_spin)
        repeat_layout.addWidget(self.repeat_unit_label)
        repeat_layout.addStretch()

        self.due_kind_combo = QComboBox()
        for kind in (DUE_KIND_NONE, DUE_KIND_DAY, DUE_KIND_FIRST_WORKING_DAY):
            self.due_kind_combo.addItem(DUE_KIND_LABELS[kind], kind)
        self.due_kind_combo.currentIndexChanged.connect(self._sync_due_controls)

        self.due_day_spin = QSpinBox()
        self.due_day_spin.setRange(1, 31)
        self.due_day_spin.setValue(1)

        form.addRow("Název:", self.title_edit)
        form.addRow("Poznámka:", self.note_edit)
        form.addRow("Rok:", self.year_combo)
        form.addRow("Měsíc:", self.month_combo)
        form.addRow("Opakovat:", self.repeat_enabled)
        form.addRow("", repeat_row)
        form.addRow("Kdy:", self.due_kind_combo)
        form.addRow("Den v měsíci:", self.due_day_spin)
        return page

    def _history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.history_empty = QLabel("Položka zatím nebyla přesunuta.")
        self.history_empty.setObjectName("MutedText")
        self.history_empty.setWordWrap(True)
        self.history_table = QTableWidget(0, len(MOVE_HISTORY_HEADERS))
        self.history_table.setHorizontalHeaderLabels(MOVE_HISTORY_HEADERS)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.history_table.setAlternatingRowColors(True)
        enable_typed_sorting(self.history_table)
        layout.addWidget(self.history_empty)
        layout.addWidget(self.history_table, 1)
        return page

    def _sync_repeat_controls(self) -> None:
        unit = self.repeat_enabled.currentData()
        enabled = unit != REPEAT_UNIT_NONE
        self.repeat_every_spin.setEnabled(enabled)
        self.repeat_unit_label.setEnabled(enabled)
        if unit == REPEAT_UNIT_YEARS:
            self.repeat_unit_label.setText(REPEAT_UNIT_LABELS[REPEAT_UNIT_YEARS])
        else:
            self.repeat_unit_label.setText(REPEAT_UNIT_LABELS[REPEAT_UNIT_MONTHS])

    def _sync_due_controls(self) -> None:
        kind = self.due_kind_combo.currentData()
        self.due_day_spin.setEnabled(kind == DUE_KIND_DAY)

    def _load_item(self, item) -> None:
        self.title_edit.setText(item.title or "")
        self.note_edit.setPlainText(item.note or "")
        year_index = self.year_combo.findData(item.year)
        if year_index >= 0:
            self.year_combo.setCurrentIndex(year_index)
        month_index = self.month_combo.findData(item.month)
        if month_index >= 0:
            self.month_combo.setCurrentIndex(month_index)

        unit = (item.repeat_unit or DEFAULT_REPEAT_UNIT).strip()
        every = int(item.repeat_every or 0)
        if every <= 0 or unit == REPEAT_UNIT_NONE:
            unit = REPEAT_UNIT_NONE
        index = self.repeat_enabled.findData(unit)
        if index >= 0:
            self.repeat_enabled.setCurrentIndex(index)
        self.repeat_every_spin.setValue(max(1, every or 1))

        kind = (item.due_kind or DEFAULT_DUE_KIND).strip()
        kind_index = self.due_kind_combo.findData(kind)
        if kind_index >= 0:
            self.due_kind_combo.setCurrentIndex(kind_index)
        if item.due_day:
            self.due_day_spin.setValue(int(item.due_day))

    def _load_history(self, item_id: int | None) -> None:
        with sorting_paused(self.history_table):
            self.history_table.setRowCount(0)
            if item_id is None:
                self.history_empty.show()
                self.history_table.hide()
                return
            rows = yearly_plan_service.get_move_history(item_id)
            if not rows:
                self.history_empty.show()
                self.history_table.hide()
                return
            self.history_empty.hide()
            self.history_table.show()
            self.history_table.setRowCount(len(rows))
            for row, move in enumerate(rows):
                from_text = format_year_month(move.from_year, move.from_month)
                to_text = format_year_month(move.to_year, move.to_month)
                when = move.moved_at
                when_text = (
                    f"{when.day:02d}.{when.month:02d}.{when.year} "
                    f"{when.hour:02d}:{when.minute:02d}"
                    if when
                    else "—"
                )
                self.history_table.setItem(
                    row,
                    0,
                    create_typed_item(from_text, typed_text(from_text)),
                )
                self.history_table.setItem(
                    row,
                    1,
                    create_typed_item(to_text, typed_text(to_text)),
                )
                self.history_table.setItem(
                    row,
                    2,
                    create_typed_item(
                        when_text,
                        typed_datetime(when) if when else typed_text(""),
                    ),
                )

    def get_data(self) -> dict:
        unit = self.repeat_enabled.currentData() or REPEAT_UNIT_NONE
        every = int(self.repeat_every_spin.value()) if unit != REPEAT_UNIT_NONE else 0
        kind = self.due_kind_combo.currentData() or DUE_KIND_NONE
        return {
            "title": self.title_edit.text().strip(),
            "note": self.note_edit.toPlainText().strip(),
            "year": int(self.year_combo.currentData()),
            "month": int(self.month_combo.currentData()),
            "repeat_every": every,
            "repeat_unit": unit,
            "due_kind": kind,
            "due_day": int(self.due_day_spin.value()) if kind == DUE_KIND_DAY else None,
        }

    def _save(self) -> bool:
        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, self.windowTitle(), TITLE_REQUIRED_MESSAGE)
            return False
        try:
            if self.item is None:
                self.item = yearly_plan_service.create(
                    year=data["year"],
                    month=data["month"],
                    title=data["title"],
                    note=data["note"],
                    status=DEFAULT_STATUS,
                    repeat_every=data["repeat_every"],
                    repeat_unit=data["repeat_unit"],
                    due_kind=data["due_kind"],
                    due_day=data["due_day"],
                )
                self._load_history(self.item.id)
            else:
                self.item = yearly_plan_service.update(
                    self.item.id,
                    year=data["year"],
                    month=data["month"],
                    title=data["title"],
                    note=data["note"],
                    status=self.item.status,
                    task_id=self.item.task_id,
                    meeting_id=self.item.meeting_id,
                    repeat_every=data["repeat_every"],
                    repeat_unit=data["repeat_unit"],
                    due_kind=data["due_kind"],
                    due_day=data["due_day"],
                )
        except YearlyPlanValidationError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        return True
