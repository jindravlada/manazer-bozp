"""Editor periodické činnosti."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.nullable_date_edit import NullableDateEdit
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
    DEFAULT_NEXT_FROM,
    DEFAULT_NOTIFY_EVERY,
    DEFAULT_NOTIFY_UNIT,
    DEFAULT_PLACE_KIND,
    DEFAULT_REPEAT_EVERY,
    DEFAULT_REPEAT_UNIT,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    ENTITY_PERIODIC_OCCURRENCE,
    HISTORY_ATTACHMENTS_HINT,
    HISTORY_ATTACHMENTS_LABEL,
    HISTORY_HEADERS,
    NEXT_FROM_LABELS,
    NEXT_FROM_VALUES,
    PLACE_KIND_LABELS,
    PLACE_KIND_OTHER,
    PLACE_KIND_WORKPLACE,
    PLACE_KINDS,
    TAB_ACTIVITY,
    TAB_HISTORY,
    TIME_UNITS,
    TITLE_REQUIRED_MESSAGE,
    UNIT_LABELS,
)
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    PeriodicActivityValidationError,
    periodic_activity_service,
)


class PeriodicActivityDialog(QDialog):
    def __init__(self, parent=None, activity=None):
        super().__init__(parent)
        self.activity = activity
        self.setWindowTitle(DIALOG_TITLE_EDIT if activity is not None else DIALOG_TITLE_NEW)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=720, height=640, min_width=520, min_height=420)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._activity_tab()), TAB_ACTIVITY)
        self.tabs.addTab(wrap_in_scroll_area(self._history_tab()), TAB_HISTORY)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=activity is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=activity is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
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
        self.next_due_edit = NullableDateEdit()

        self.repeat_every = QSpinBox()
        self.repeat_every.setRange(1, 9999)
        self.repeat_every.setValue(DEFAULT_REPEAT_EVERY)
        self.repeat_unit = QComboBox()
        for unit in TIME_UNITS:
            self.repeat_unit.addItem(UNIT_LABELS[unit], unit)
        self.repeat_unit.setCurrentIndex(TIME_UNITS.index(DEFAULT_REPEAT_UNIT))
        repeat_row = QHBoxLayout()
        repeat_row.addWidget(self.repeat_every)
        repeat_row.addWidget(self.repeat_unit, 1)
        repeat_widget = QWidget()
        repeat_widget.setLayout(repeat_row)

        self.notify_every = QSpinBox()
        self.notify_every.setRange(0, 9999)
        self.notify_every.setValue(DEFAULT_NOTIFY_EVERY)
        self.notify_unit = QComboBox()
        for unit in TIME_UNITS:
            self.notify_unit.addItem(UNIT_LABELS[unit], unit)
        self.notify_unit.setCurrentIndex(TIME_UNITS.index(DEFAULT_NOTIFY_UNIT))
        notify_row = QHBoxLayout()
        notify_row.addWidget(self.notify_every)
        notify_row.addWidget(self.notify_unit, 1)
        notify_row.addWidget(QLabel("před termínem"))
        notify_widget = QWidget()
        notify_widget.setLayout(notify_row)

        self.next_from = QComboBox()
        for value in NEXT_FROM_VALUES:
            self.next_from.addItem(NEXT_FROM_LABELS[value], value)
        self.next_from.setCurrentIndex(NEXT_FROM_VALUES.index(DEFAULT_NEXT_FROM))

        self.note_edit = QTextEdit()
        self.note_edit.setAcceptRichText(False)
        self.note_edit.setMinimumHeight(90)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název:", self.title_edit)
        form.addRow("Místo:", self.place_kind)
        form.addRow("", self.workplace_selector)
        form.addRow("", self.place_text)
        form.addRow("Odpovědná osoba:", self.responsible_selector)
        form.addRow("Nejbližší termín:", self.next_due_edit)
        form.addRow("Opakovat každých:", repeat_widget)
        form.addRow("Upozornit:", notify_widget)
        form.addRow("Další termín počítat od:", self.next_from)
        form.addRow("Poznámka:", self.note_edit)
        form.addRow("", self.active_checkbox)
        return page

    def _history_tab(self) -> QWidget:
        page = QWidget()
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
        enable_typed_sorting(self.history_table)
        self.history_table.itemSelectionChanged.connect(self._on_history_selection_changed)

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
        self.next_due_edit.set_date_value(activity.next_due_date)
        self.repeat_every.setValue(activity.repeat_every or DEFAULT_REPEAT_EVERY)
        unit_index = self.repeat_unit.findData(activity.repeat_unit or DEFAULT_REPEAT_UNIT)
        if unit_index >= 0:
            self.repeat_unit.setCurrentIndex(unit_index)
        self.notify_every.setValue(activity.notify_every if activity.notify_every is not None else 0)
        notify_index = self.notify_unit.findData(activity.notify_unit or DEFAULT_NOTIFY_UNIT)
        if notify_index >= 0:
            self.notify_unit.setCurrentIndex(notify_index)
        next_index = self.next_from.findData(activity.next_from or DEFAULT_NEXT_FROM)
        if next_index >= 0:
            self.next_from.setCurrentIndex(next_index)
        self.note_edit.setPlainText(activity.note or "")
        self.active_checkbox.setChecked(bool(activity.active))
        self._sync_place_fields()

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
                self.history_table.setItem(row, 0, planned_item)

                performed = occurrence.performed_at
                performed_text = f"{performed.day:02d}.{performed.month:02d}.{performed.year}"
                self.history_table.setItem(
                    row,
                    1,
                    create_typed_item(
                        performed_text,
                        typed_datetime(datetime.combine(performed, time.min)),
                    ),
                )
                who = (occurrence.performed_by_name or "").strip() or "—"
                self.history_table.setItem(
                    row,
                    2,
                    create_typed_item(who, typed_text(who)),
                )
                note = (occurrence.result_note or "").strip() or "—"
                self.history_table.setItem(
                    row,
                    3,
                    create_typed_item(note, typed_text(note)),
                )
        self._clear_history_attachments()

    def _selected_occurrence_id(self) -> int | None:
        rows = self.history_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.history_table.item(rows[0].row(), 0)
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

    def get_data(self) -> dict:
        worker = self.responsible_selector.current_person()
        worker_id = self.responsible_selector.current_person_id()
        worker_name = worker.display_name if worker else self.responsible_selector.currentText().strip()
        workplace_id = self.workplace_selector.current_workplace_id()
        return {
            "title": self.title_edit.text().strip(),
            "place_kind": self.place_kind.currentData() or DEFAULT_PLACE_KIND,
            "workplace_id": workplace_id,
            "workplace_name": "",
            "place_text": self.place_text.text().strip(),
            "responsible_person_id": worker_id,
            "responsible_person_name": worker_name,
            "next_due_date": self.next_due_edit.get_date(),
            "repeat_every": int(self.repeat_every.value()),
            "repeat_unit": self.repeat_unit.currentData() or DEFAULT_REPEAT_UNIT,
            "notify_every": int(self.notify_every.value()),
            "notify_unit": self.notify_unit.currentData() or DEFAULT_NOTIFY_UNIT,
            "next_from": self.next_from.currentData() or DEFAULT_NEXT_FROM,
            "note": self.note_edit.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }

    def _save(self) -> bool:
        data = self.get_data()
        if not data["title"]:
            QMessageBox.warning(self, self.windowTitle(), TITLE_REQUIRED_MESSAGE)
            return False
        try:
            if self.activity is None:
                self.activity = periodic_activity_service.create_activity(**data)
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
