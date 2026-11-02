"""Editor periodické činnosti."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.table_utils import refresh_elided_cell_tooltips
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
)
from moduly.periodicke_cinnosti.ui.save_confirmation import ConfirmingSaveController
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_empty,
    typed_text,
)
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.periodicke_cinnosti.constants import (
    CALENDAR_MONTH_NAMES,
    CALENDAR_MONTH_UNSET,
    CALENDAR_REQUIRED_MESSAGE,
    CALENDAR_SETUP_WARNING,
    CALENDAR_VALUE_UNSET,
    DEFAULT_CALENDAR_INTERVAL_MONTHS,
    DEFAULT_NEXT_FROM,
    DEFAULT_NOTIFY_EVERY,
    DEFAULT_NOTIFY_UNIT,
    DEFAULT_PLACE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
    MAX_CALENDAR_YEAR,
    MIN_CALENDAR_YEAR,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    ENTITY_PERIODIC_OCCURRENCE,
    HISTORY_ATTACHMENTS_HINT,
    HISTORY_ATTACHMENTS_LABEL,
    HISTORY_COL_NOTE,
    HISTORY_COL_PERFORMED,
    HISTORY_COL_PERFORMER,
    HISTORY_COL_PLANNED,
    HISTORY_HEADERS,
    PLACE_KIND_LABELS,
    PLACE_KIND_OTHER,
    PLACE_KIND_WORKPLACE,
    PLACE_KINDS,
    TAB_ACTIVITY,
    TAB_HISTORY,
    TITLE_REQUIRED_MESSAGE,
    UNIT_DAYS,
    UNIT_WEEKS,
)
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    PeriodicActivityValidationError,
    periodic_activity_service,
)

_SAVE_CLOSE_LABEL = "Uložit a zavřít"
_UNSAVED_ABORT_LABEL = "Zpět"
_HISTORY_DATE_SAMPLE = "31.12.2026 23:59"
_HISTORY_NAME_SAMPLE = "Jméno Příjmení Pracovníka"


class PeriodicActivityDialog(QDialog):
    def __init__(self, parent=None, activity=None):
        super().__init__(parent)
        self.activity = activity
        self._calendar_setup_required = False
        self.setWindowTitle(DIALOG_TITLE_EDIT if activity is not None else DIALOG_TITLE_NEW)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=720, height=640, min_width=520, min_height=420)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._activity_tab()), TAB_ACTIVITY)
        self.tabs.addTab(wrap_in_scroll_area(self._history_tab()), TAB_HISTORY)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=activity is None)
        self._editor = ConfirmingSaveController(
            self,
            buttons,
            is_new=activity is None,
            title=self.windowTitle(),
            on_save=self._save,
            unsaved_abort_label=_UNSAVED_ABORT_LABEL,
        )
        configure_editor_close_button(self._editor.close_button, is_new=False)
        if self._editor.close_button is not None:
            self._editor.close_button.setText(EDITOR_CLOSE_LABEL)
        layout.addLayout(self._build_footer(buttons))
        buttons.hide()
        for button in (
            self._editor.save_button,
            self._save_close_btn,
            self._editor.close_button,
        ):
            if button is not None:
                button.setVisible(True)
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        self.place_kind.currentIndexChanged.connect(self._sync_place_fields)
        self._sync_place_fields()

        if activity is not None:
            self._load_activity(activity)
            self._load_history(activity.id)
        else:
            self._load_history(None)

        self._editor.capture_baseline()

    def _activity_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.title_edit = QLineEdit()
        self.place_kind = QComboBox()
        for kind in PLACE_KINDS:
            self.place_kind.addItem(PLACE_KIND_LABELS[kind], kind)

        self.workplace_selector = WorkplaceSelector()
        self.place_text = QLineEdit()
        self.place_text.setPlaceholderText("Místo mimo organizaci")

        self.responsible_selector = ThpWorkerSelector(include_empty=True)

        self.calendar_setup_warning = QLabel(CALENDAR_SETUP_WARNING)
        self.calendar_setup_warning.setObjectName("MutedText")
        self.calendar_setup_warning.setWordWrap(True)
        self.calendar_setup_warning.hide()

        self.calendar_month = QComboBox()
        self.calendar_month.addItem(CALENDAR_MONTH_UNSET, None)
        for index, name in enumerate(CALENDAR_MONTH_NAMES, start=1):
            self.calendar_month.addItem(name, index)

        self.calendar_year = QSpinBox()
        self.calendar_year.setRange(MIN_CALENDAR_YEAR - 1, MAX_CALENDAR_YEAR)
        self.calendar_year.setSpecialValueText(CALENDAR_VALUE_UNSET)

        self.calendar_interval = QSpinBox()
        self.calendar_interval.setRange(0, 2147483647)
        self.calendar_interval.setSpecialValueText(CALENDAR_VALUE_UNSET)
        self._set_calendar_defaults()

        self.note_edit = QTextEdit()
        self.note_edit.setAcceptRichText(False)
        self.note_edit.setMinimumHeight(90)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        repeat_heading = QLabel("Opakování v Ročním plánu")
        repeat_heading.setObjectName("MutedText")
        form.addRow("Název:", self.title_edit)
        form.addRow("Poznámka:", self.note_edit)
        form.addRow("Místo:", self.place_kind)
        form.addRow("", self.workplace_selector)
        form.addRow("", self.place_text)
        form.addRow("Odpovědná osoba:", self.responsible_selector)
        form.addRow("", self.active_checkbox)
        form.addRow(repeat_heading)
        form.addRow(self.calendar_setup_warning)
        form.addRow("Počáteční měsíc:", self.calendar_month)
        form.addRow("Počáteční rok:", self.calendar_year)
        form.addRow("Interval v měsících:", self.calendar_interval)
        self.calendar_month.currentIndexChanged.connect(self._refresh_calendar_warning)
        self.calendar_year.valueChanged.connect(self._refresh_calendar_warning)
        self.calendar_interval.valueChanged.connect(self._refresh_calendar_warning)
        self._refresh_calendar_warning()
        return page

    def _history_tab(self) -> QWidget:
        page = QWidget()
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        self.history_empty = QLabel("Zatím není evidováno žádné provedení.")
        self.history_empty.setObjectName("MutedText")
        self.history_empty.setWordWrap(True)
        self.history_table = QTableWidget(0, len(HISTORY_HEADERS))
        self.history_table.setHorizontalHeaderLabels(HISTORY_HEADERS)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setAlternatingRowColors(True)
        self._configure_history_table()
        enable_typed_sorting(self.history_table)
        self.history_table.itemSelectionChanged.connect(self._on_history_selection_changed)
        self.history_table.horizontalHeader().sectionResized.connect(
            self._refresh_history_note_tooltips
        )
        self.history_table.installEventFilter(self)

        self.history_attachments_hint = QLabel(HISTORY_ATTACHMENTS_HINT)
        self.history_attachments_hint.setObjectName("MutedText")
        self.history_attachments_hint.setWordWrap(True)
        self.history_attachments_label = QLabel(HISTORY_ATTACHMENTS_LABEL)
        self.history_attachments = AttachmentWidget(ENTITY_PERIODIC_OCCURRENCE, None)

        layout.addWidget(self.history_empty)
        layout.addWidget(self.history_table, 1)
        layout.addWidget(self.history_attachments_hint)
        layout.addWidget(self.history_attachments_label)
        layout.addWidget(self.history_attachments, 1)
        return page

    def _set_calendar_defaults(self) -> None:
        today = date.today()
        month_index = self.calendar_month.findData(today.month)
        if month_index >= 0:
            self.calendar_month.setCurrentIndex(month_index)
        self.calendar_year.setValue(today.year)
        self.calendar_interval.setValue(DEFAULT_CALENDAR_INTERVAL_MONTHS)

    def _clear_calendar_fields(self) -> None:
        unset = self.calendar_month.findData(None)
        self.calendar_month.setCurrentIndex(unset if unset >= 0 else 0)
        self.calendar_year.setValue(MIN_CALENDAR_YEAR - 1)
        self.calendar_interval.setValue(0)

    def _load_calendar(self, activity) -> None:
        year = getattr(activity, "calendar_start_year", None)
        month = getattr(activity, "calendar_start_month", None)
        interval = getattr(activity, "calendar_interval_months", None)
        if year is None or month is None or interval is None:
            self._clear_calendar_fields()
            return
        month_index = self.calendar_month.findData(int(month))
        if month_index >= 0:
            self.calendar_month.setCurrentIndex(month_index)
        self.calendar_year.setValue(int(year))
        self.calendar_interval.setValue(int(interval))

    def _calendar_year_value(self) -> int | None:
        year = int(self.calendar_year.value())
        if year < MIN_CALENDAR_YEAR:
            return None
        return year

    def _calendar_interval_value(self) -> int | None:
        interval = int(self.calendar_interval.value())
        if interval < 1:
            return None
        return interval

    def _calendar_is_complete(self) -> bool:
        return (
            self.calendar_month.currentData() is not None
            and self._calendar_year_value() is not None
            and self._calendar_interval_value() is not None
        )

    def _stored_repeat_unit(self) -> str:
        if self.activity is None:
            return ""
        return (self.activity.repeat_unit or "").strip()

    def _calendar_setup_flag(self) -> bool:
        if self._calendar_is_complete():
            return False
        legacy = self._stored_repeat_unit() in {UNIT_DAYS, UNIT_WEEKS}
        return bool(self._calendar_setup_required) or legacy

    def _refresh_calendar_warning(self, *_args) -> None:
        self.calendar_setup_warning.setVisible(
            self.activity is not None
            and not self._calendar_is_complete()
            and self._calendar_setup_flag()
        )

    def _sync_place_fields(self) -> None:
        kind = self.place_kind.currentData()
        self.workplace_selector.setVisible(kind == PLACE_KIND_WORKPLACE)
        self.place_text.setVisible(kind == PLACE_KIND_OTHER)

    def _load_activity(self, activity) -> None:
        self.title_edit.setText(activity.title or "")
        index = self.place_kind.findData(activity.place_kind or DEFAULT_PLACE_KIND)
        if index >= 0:
            self.place_kind.setCurrentIndex(index)
        self.workplace_selector.set_workplace_id(
            activity.workplace_id,
            workplace_name=activity.workplace_name or "",
        )
        self.place_text.setText(activity.place_text or "")
        self.responsible_selector.set_person_id(activity.responsible_person_id)
        self._calendar_setup_required = bool(getattr(activity, "calendar_setup_required", False))
        self._load_calendar(activity)
        self.note_edit.setPlainText(activity.note or "")
        self.active_checkbox.setChecked(bool(activity.active))
        self._sync_place_fields()
        self._refresh_calendar_warning()

    def _load_history(self, activity_id: int | None) -> None:
        with sorting_paused(self.history_table):
            self.history_table.setRowCount(0)
            if activity_id is None:
                self.history_empty.show()
                self.history_table.hide()
                self._clear_history_attachments()
                return
            rows = periodic_activity_service.list_occurrences(activity_id)
            if not rows:
                self.history_empty.show()
                self.history_table.hide()
                self._clear_history_attachments()
                return
            self.history_empty.hide()
            self.history_table.show()
            self.history_table.setRowCount(len(rows))
            for row, occurrence in enumerate(rows):
                planned = occurrence.planned_due_date
                planned_text = (
                    f"{planned.day:02d}.{planned.month:02d}.{planned.year}"
                    if planned
                    else "—"
                )
                planned_sort = (
                    typed_datetime(datetime.combine(planned, time.min))
                    if planned
                    else typed_empty()
                )
                planned_item = create_typed_item(planned_text, planned_sort)
                planned_item.setData(Qt.ItemDataRole.UserRole, occurrence.id)
                self.history_table.setItem(row, HISTORY_COL_PLANNED, planned_item)

                performed = occurrence.performed_at
                performed_text = f"{performed.day:02d}.{performed.month:02d}.{performed.year}"
                self.history_table.setItem(
                    row,
                    HISTORY_COL_PERFORMED,
                    create_typed_item(
                        performed_text,
                        typed_datetime(datetime.combine(performed, time.min)),
                    ),
                )
                who = (occurrence.performed_by_name or "").strip() or "—"
                self.history_table.setItem(
                    row,
                    HISTORY_COL_PERFORMER,
                    create_typed_item(who, typed_text(who)),
                )
                note = (occurrence.result_note or "").strip() or "—"
                self.history_table.setItem(
                    row,
                    HISTORY_COL_NOTE,
                    create_typed_item(note, typed_text(note)),
                )
            self._refresh_history_note_tooltips()
        self._clear_history_attachments()

    def _configure_history_table(self) -> None:
        """Tabulka vyplní šířku záložky; poznámka bere zbytek, data a jméno zůstanou čitelná."""
        table = self.history_table
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        date_width = max(
            self._history_text_width(HISTORY_HEADERS[HISTORY_COL_PLANNED], header=True),
            self._history_text_width(HISTORY_HEADERS[HISTORY_COL_PERFORMED], header=True),
            self._history_text_width(_HISTORY_DATE_SAMPLE),
        )
        name_width = max(
            self._history_text_width(HISTORY_HEADERS[HISTORY_COL_PERFORMER], header=True),
            self._history_text_width(_HISTORY_NAME_SAMPLE),
        )
        header.setMinimumSectionSize(date_width)
        table.setColumnWidth(HISTORY_COL_PLANNED, date_width)
        table.setColumnWidth(HISTORY_COL_PERFORMED, date_width)
        table.setColumnWidth(HISTORY_COL_PERFORMER, name_width)
        for column in (HISTORY_COL_PLANNED, HISTORY_COL_PERFORMED, HISTORY_COL_PERFORMER):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(HISTORY_COL_NOTE, QHeaderView.ResizeMode.Stretch)

        metrics = table.fontMetrics()
        row_height = max(metrics.lineSpacing(), metrics.height()) + 8
        vertical = table.verticalHeader()
        vertical.setMinimumSectionSize(row_height)
        vertical.setDefaultSectionSize(row_height)
        vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setMinimumHeight(row_height)

    def _history_text_width(self, text: str, *, header: bool = False) -> int:
        table = self.history_table
        metrics = table.horizontalHeader().fontMetrics() if header else table.fontMetrics()
        sort_mark = 0
        if header:
            sort_mark = table.style().pixelMetric(
                QStyle.PixelMetric.PM_HeaderMarkSize,
                None,
                table.horizontalHeader(),
            )
        return metrics.horizontalAdvance(text) + sort_mark + 28

    def _refresh_history_note_tooltips(self, *_args) -> None:
        refresh_elided_cell_tooltips(self.history_table, (HISTORY_COL_NOTE,))

    def eventFilter(self, watched, event) -> bool:
        if watched is getattr(self, "history_table", None) and event.type() == QEvent.Type.Resize:
            self._refresh_history_note_tooltips()
        return super().eventFilter(watched, event)

    def _selected_occurrence_id(self) -> int | None:
        rows = self.history_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.history_table.item(rows[0].row(), HISTORY_COL_PLANNED)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _clear_history_attachments(self) -> None:
        self.history_attachments.set_entity(ENTITY_PERIODIC_OCCURRENCE, None)
        self.history_attachments_hint.setText(HISTORY_ATTACHMENTS_HINT)
        self.history_attachments_hint.show()

    def _on_history_selection_changed(self) -> None:
        occurrence_id = self._selected_occurrence_id()
        if occurrence_id is None:
            self._clear_history_attachments()
            return
        self.history_attachments_hint.hide()
        self.history_attachments.set_entity(ENTITY_PERIODIC_OCCURRENCE, occurrence_id)

    def _build_footer(self, buttons) -> QHBoxLayout:
        """Uložit | Uložit a zavřít | Zavřít vpravo."""
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)

        self._save_close_btn = QPushButton(_SAVE_CLOSE_LABEL)
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(_SAVE_CLOSE_LABEL)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._editor.bind_extra_save_button(self._save_close_btn)

        ordered = [
            self._editor.save_button,
            self._save_close_btn,
            self._editor.close_button,
        ]
        for button in ordered:
            if button is None:
                continue
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setAutoDefault(False)
            button.setDefault(False)
            footer.addWidget(button)
        self._button_box = buttons
        return footer

    def _save_and_close(self) -> None:
        if not self._editor._run_save():
            return
        self._editor._closing = True
        QDialog.accept(self)

    def _legacy_fields(self) -> dict:
        """Skrytá historická pole. Běžné uložení jim nedává nové výchozí hodnoty."""
        activity = self.activity
        if activity is None:
            return {
                "next_due_date": None,
                "repeat_every": DEFAULT_REPEAT_EVERY,
                "repeat_unit": DEFAULT_REPEAT_UNIT,
                "notify_every": DEFAULT_NOTIFY_EVERY,
                "notify_unit": DEFAULT_NOTIFY_UNIT,
                "next_from": DEFAULT_NEXT_FROM,
            }
        return {
            "next_due_date": activity.next_due_date,
            "repeat_every": int(activity.repeat_every or DEFAULT_REPEAT_EVERY),
            "repeat_unit": activity.repeat_unit or DEFAULT_REPEAT_UNIT,
            "notify_every": int(
                activity.notify_every if activity.notify_every is not None else DEFAULT_NOTIFY_EVERY
            ),
            "notify_unit": activity.notify_unit or DEFAULT_NOTIFY_UNIT,
            "next_from": activity.next_from or DEFAULT_NEXT_FROM,
        }

    def get_data(self) -> dict:
        worker = self.responsible_selector.current_person()
        worker_id = self.responsible_selector.current_person_id()
        worker_name = worker.display_name if worker else self.responsible_selector.currentText().strip()
        workplace_id = self.workplace_selector.current_workplace_id()
        data = {
            "title": self.title_edit.text().strip(),
            "place_kind": self.place_kind.currentData() or DEFAULT_PLACE_KIND,
            "workplace_id": workplace_id,
            "workplace_name": "",
            "place_text": self.place_text.text().strip(),
            "responsible_person_id": worker_id,
            "responsible_person_name": worker_name,
            "calendar_start_year": self._calendar_year_value(),
            "calendar_start_month": self.calendar_month.currentData(),
            "calendar_interval_months": self._calendar_interval_value(),
            "calendar_setup_required": self._calendar_setup_flag(),
            "note": self.note_edit.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
        data.update(self._legacy_fields())
        return data

    def _save(self) -> bool:
        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, self.windowTitle(), TITLE_REQUIRED_MESSAGE)
            return False
        if not self._calendar_is_complete() and (
            self.activity is None or self._activity_has_calendar()
        ):
            QMessageBox.warning(self, self.windowTitle(), CALENDAR_REQUIRED_MESSAGE)
            return False
        creating = self.activity is None
        try:
            if creating:
                self.activity = periodic_activity_service.create_activity(**data)
                self.setWindowTitle(DIALOG_TITLE_EDIT)
                self._editor._title = DIALOG_TITLE_EDIT
                self._load_history(self.activity.id)
            else:
                self.activity = periodic_activity_service.update_activity(
                    self.activity.id,
                    **data,
                )
        except PeriodicActivityValidationError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        return True

    def _activity_has_calendar(self) -> bool:
        activity = self.activity
        if activity is None:
            return False
        return (
            activity.calendar_start_year is not None
            and activity.calendar_start_month is not None
            and activity.calendar_interval_months is not None
        )
