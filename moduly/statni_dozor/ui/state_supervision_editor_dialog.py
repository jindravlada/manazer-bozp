"""Editor kontroly státního dozoru — základ a záložka Ohlášení a zahájení."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import (
    EditorDialogController,
    configure_editor_save_button,
)
from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
from core.widgets.search_combo_box import SearchComboBox
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    ACTION_SAVE_AND_CLOSE,
    AUTHORITY_REQUIRED_MESSAGE,
    AUTHORITY_SUGGESTIONS,
    DEFAULT_STATUS,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    ENDED_BEFORE_STARTED_MESSAGE,
    GROUP_ACTUAL_COURSE,
    GROUP_INFORMING,
    GROUP_NOTIFICATION,
    GROUP_PLANNED_START,
    GROUP_REPRESENTATION,
    LABEL_ANNOUNCED_AT,
    LABEL_AUTHORITY,
    LABEL_AUTHORITY_ADDRESS,
    LABEL_AUTHORITY_ICO,
    LABEL_ENDED_AT,
    LABEL_FILE_NUMBER,
    LABEL_MANAGEMENT_NOTIFIED_AT,
    LABEL_NOTIFICATION_METHOD,
    LABEL_NOTIFICATION_NOTE,
    LABEL_PLANNED_CONTROL_PLACE,
    LABEL_PLANNED_START_AT,
    LABEL_PLANNED_START_PLACE,
    LABEL_POWER_OF_ATTORNEY,
    LABEL_POWER_OF_ATTORNEY_NOTE,
    LABEL_STARTED_AT,
    LABEL_STATUS,
    LABEL_TRADE_UNION_NOTIFIED_AT,
    LABEL_WORKPLACE,
    NOTIFICATION_METHOD_EMPTY_LABEL,
    SAVE_ERROR_MESSAGE,
    STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS,
    STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER,
    STATE_SUPERVISION_STATUS_LABELS,
    STATE_SUPERVISION_STATUS_ORDER,
    TAB_ANNOUNCEMENT,
)
from moduly.statni_dozor.modely.state_supervision import StateSupervision
from moduly.statni_dozor.sluzby.state_supervision_service import (
    StateSupervisionError,
    state_supervision_service,
)

logger = logging.getLogger(__name__)

_EDITOR_FIELDS = (
    "status",
    "authority_ico",
    "authority_name",
    "authority_address",
    "workplace_id",
    "workplace_name_snapshot",
    "workplace_address_snapshot",
    "notification_method",
    "announced_at",
    "notification_note",
    "trade_union_notified_at",
    "management_notified_at",
    "planned_start_at",
    "planned_start_place",
    "planned_control_place",
    "started_at",
    "ended_at",
    "file_number",
    "power_of_attorney_required",
    "power_of_attorney_note",
)


class _SupervisionEditorController(EditorDialogController):
    """Stejná aktivace Uložit i pro tlačítko Uložit a zavřít."""

    def __init__(self, *args, extra_save_buttons=(), **kwargs):
        self._extra_save_buttons = list(extra_save_buttons)
        super().__init__(*args, **kwargs)

    def _refresh_save_enabled(self) -> None:
        super()._refresh_save_enabled()
        enabled = bool(self.save_button is not None and self.save_button.isEnabled())
        for button in self._extra_save_buttons:
            button.setEnabled(enabled)


def _short_note_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setMinimumHeight(52)
    edit.setMaximumHeight(78)
    return edit


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(microsecond=0)


class StateSupervisionEditorDialog(QDialog):
    def __init__(self, parent=None, *, supervision_id: int | None = None):
        super().__init__(parent)
        self._record: StateSupervision | None = None
        self._supervision_id = supervision_id
        self._persisted = False
        self._loaded_workplace_id: int | None = None
        self._loaded_name_snapshot = ""
        self._loaded_address_snapshot = ""

        if supervision_id is not None:
            self._record = state_supervision_service.get_supervision(supervision_id)
            if self._record is not None:
                self._supervision_id = int(self._record.id)

        is_existing = self._record is not None
        self.setWindowTitle(DIALOG_TITLE_EDIT if is_existing else DIALOG_TITLE_NEW)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=980, height=720, min_width=640, min_height=480)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_header())
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._build_announcement_tab()), TAB_ANNOUNCEMENT)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(self._build_footer())

        configure_form_tab_navigation(self)

        # is_new=False: Uložit řídí snapshot != baseline i u nové kontroly.
        self._editor = _SupervisionEditorController(
            self,
            self._buttons,
            is_new=False,
            title=self.windowTitle(),
            on_save=self._persist,
            extra_save_buttons=(self._save_close_btn,),
        )
        self._editor.set_snapshot_provider(self.get_snapshot)
        self._editor.install_auto_dirty_tracking()
        for widget in self._datetime_widgets():
            widget.dateTimeChanged.connect(self._editor.refresh_dirty)

        if self._record is not None:
            self._apply_record(self._record)
        else:
            self._set_combo_data(self.status_combo, DEFAULT_STATUS)

        self._editor.capture_baseline()

    @property
    def saved(self) -> bool:
        return self._persisted

    @property
    def supervision_id(self) -> int | None:
        if self._supervision_id is not None:
            return int(self._supervision_id)
        if self._record is not None:
            return int(self._record.id)
        return None

    def _build_header(self) -> QWidget:
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)

        self.authority_combo = SearchComboBox(values=list(AUTHORITY_SUGGESTIONS))
        self.authority_combo.setCurrentText("")
        self.ico_edit = QLineEdit()
        self.address_edit = QLineEdit()
        self.workplace_selector = WorkplaceSelector(include_empty=True)
        self.status_combo = QComboBox()
        for status in STATE_SUPERVISION_STATUS_ORDER:
            self.status_combo.addItem(STATE_SUPERVISION_STATUS_LABELS[status], status)
        self._set_combo_data(self.status_combo, DEFAULT_STATUS)

        form.addRow(f"{LABEL_AUTHORITY}:", self.authority_combo)
        form.addRow(f"{LABEL_AUTHORITY_ICO}:", self.ico_edit)
        form.addRow(f"{LABEL_AUTHORITY_ADDRESS}:", self.address_edit)
        form.addRow(f"{LABEL_WORKPLACE}:", self.workplace_selector)
        form.addRow(f"{LABEL_STATUS}:", self.status_combo)
        return host

    def _build_announcement_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        notification = QGroupBox(GROUP_NOTIFICATION)
        notification_form = QFormLayout(notification)
        self.notification_method_combo = QComboBox()
        self.notification_method_combo.addItem(NOTIFICATION_METHOD_EMPTY_LABEL, None)
        for method in STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER:
            self.notification_method_combo.addItem(
                STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS[method],
                method,
            )
        self.announced_at_edit = NullableDateTimeEdit()
        self.file_number_edit = QLineEdit()
        self.notification_note_edit = _short_note_edit()
        notification_form.addRow(f"{LABEL_NOTIFICATION_METHOD}:", self.notification_method_combo)
        notification_form.addRow(f"{LABEL_ANNOUNCED_AT}:", self.announced_at_edit)
        notification_form.addRow(f"{LABEL_FILE_NUMBER}:", self.file_number_edit)
        notification_form.addRow(f"{LABEL_NOTIFICATION_NOTE}:", self.notification_note_edit)

        planned = QGroupBox(GROUP_PLANNED_START)
        planned_form = QFormLayout(planned)
        self.planned_start_at_edit = NullableDateTimeEdit()
        self.planned_start_place_edit = QLineEdit()
        self.planned_control_place_edit = QLineEdit()
        planned_form.addRow(f"{LABEL_PLANNED_START_AT}:", self.planned_start_at_edit)
        planned_form.addRow(f"{LABEL_PLANNED_START_PLACE}:", self.planned_start_place_edit)
        planned_form.addRow(f"{LABEL_PLANNED_CONTROL_PLACE}:", self.planned_control_place_edit)

        actual = QGroupBox(GROUP_ACTUAL_COURSE)
        actual_form = QFormLayout(actual)
        self.started_at_edit = NullableDateTimeEdit()
        self.ended_at_edit = NullableDateTimeEdit()
        actual_form.addRow(f"{LABEL_STARTED_AT}:", self.started_at_edit)
        actual_form.addRow(f"{LABEL_ENDED_AT}:", self.ended_at_edit)

        informing = QGroupBox(GROUP_INFORMING)
        informing_form = QFormLayout(informing)
        self.trade_union_notified_at_edit = NullableDateTimeEdit()
        self.management_notified_at_edit = NullableDateTimeEdit()
        informing_form.addRow(
            f"{LABEL_TRADE_UNION_NOTIFIED_AT}:",
            self.trade_union_notified_at_edit,
        )
        informing_form.addRow(
            f"{LABEL_MANAGEMENT_NOTIFIED_AT}:",
            self.management_notified_at_edit,
        )

        representation = QGroupBox(GROUP_REPRESENTATION)
        representation_form = QFormLayout(representation)
        self.power_of_attorney_checkbox = QCheckBox(LABEL_POWER_OF_ATTORNEY)
        self.power_of_attorney_note_edit = _short_note_edit()
        representation_form.addRow("", self.power_of_attorney_checkbox)
        representation_form.addRow(
            f"{LABEL_POWER_OF_ATTORNEY_NOTE}:",
            self.power_of_attorney_note_edit,
        )

        layout.addWidget(notification)
        layout.addWidget(planned)
        layout.addWidget(actual)
        layout.addWidget(informing)
        layout.addWidget(representation)
        layout.addStretch(1)
        return page

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)

        self._buttons = create_save_cancel_box(self, is_new=False)
        self._save_close_btn = QPushButton()
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(ACTION_SAVE_AND_CLOSE)
        self._save_close_btn.setAutoDefault(False)
        self._save_close_btn.setDefault(False)
        self._save_close_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._buttons.addButton(self._save_close_btn, QDialogButtonBox.ButtonRole.ApplyRole)
        self._save_close_btn.clicked.connect(self._save_and_close)
        footer.addWidget(self._buttons)
        return footer

    def _datetime_widgets(self) -> tuple[NullableDateTimeEdit, ...]:
        return (
            self.announced_at_edit,
            self.planned_start_at_edit,
            self.started_at_edit,
            self.ended_at_edit,
            self.trade_union_notified_at_edit,
            self.management_notified_at_edit,
        )

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply_record(self, record: StateSupervision) -> None:
        self._record = record
        self._supervision_id = int(record.id)
        self._loaded_workplace_id = (
            int(record.workplace_id) if record.workplace_id else None
        )
        self._loaded_name_snapshot = str(record.workplace_name_snapshot or "")
        self._loaded_address_snapshot = str(record.workplace_address_snapshot or "")

        blockers = [
            self.authority_combo,
            self.ico_edit,
            self.address_edit,
            self.workplace_selector,
            self.status_combo,
            self.notification_method_combo,
            self.file_number_edit,
            self.notification_note_edit,
            self.planned_start_place_edit,
            self.planned_control_place_edit,
            self.power_of_attorney_checkbox,
            self.power_of_attorney_note_edit,
            *self._datetime_widgets(),
        ]
        for widget in blockers:
            widget.blockSignals(True)
        try:
            self.authority_combo.setCurrentText(str(record.authority_name or ""))
            self.ico_edit.setText(str(record.authority_ico or ""))
            self.address_edit.setText(str(record.authority_address or ""))
            self.workplace_selector.set_workplace_id(
                record.workplace_id,
                workplace_name=str(record.workplace_name_snapshot or ""),
            )
            self._set_combo_data(self.status_combo, record.status or DEFAULT_STATUS)
            self._set_combo_data(self.notification_method_combo, record.notification_method)
            self.announced_at_edit.set_datetime(_normalize_datetime(record.announced_at))
            self.file_number_edit.setText(str(record.file_number or ""))
            self.notification_note_edit.setPlainText(str(record.notification_note or ""))
            self.planned_start_at_edit.set_datetime(
                _normalize_datetime(record.planned_start_at)
            )
            self.planned_start_place_edit.setText(str(record.planned_start_place or ""))
            self.planned_control_place_edit.setText(str(record.planned_control_place or ""))
            self.started_at_edit.set_datetime(_normalize_datetime(record.started_at))
            self.ended_at_edit.set_datetime(_normalize_datetime(record.ended_at))
            self.trade_union_notified_at_edit.set_datetime(
                _normalize_datetime(record.trade_union_notified_at)
            )
            self.management_notified_at_edit.set_datetime(
                _normalize_datetime(record.management_notified_at)
            )
            self.power_of_attorney_checkbox.setChecked(bool(record.power_of_attorney_required))
            self.power_of_attorney_note_edit.setPlainText(
                str(record.power_of_attorney_note or "")
            )
        finally:
            for widget in blockers:
                widget.blockSignals(False)

    def _workplace_payload(self) -> tuple[int | None, str, str]:
        workplace_id = self.workplace_selector.current_workplace_id()
        if workplace_id is not None:
            workplace_id = int(workplace_id)
            if workplace_id == self._loaded_workplace_id:
                return (
                    workplace_id,
                    self._loaded_name_snapshot,
                    self._loaded_address_snapshot,
                )
            workplace = settings_service.get_workplace_by_id(workplace_id)
            if workplace is None:
                return workplace_id, self.workplace_selector.display_text(), ""
            return (
                workplace_id,
                str(workplace.name or "").strip(),
                str(workplace.address or "").strip(),
            )
        text = self.workplace_selector.display_text()
        if not text:
            return None, "", ""
        return None, text, ""

    def get_data(self) -> dict:
        workplace_id, name_snapshot, address_snapshot = self._workplace_payload()
        status = self.status_combo.currentData() or DEFAULT_STATUS
        method = self.notification_method_combo.currentData()
        return {
            "authority_name": self.authority_combo.currentText().strip(),
            "authority_ico": self.ico_edit.text().strip(),
            "authority_address": self.address_edit.text().strip(),
            "workplace_id": workplace_id,
            "workplace_name_snapshot": name_snapshot,
            "workplace_address_snapshot": address_snapshot,
            "status": str(status),
            "notification_method": str(method) if method else None,
            "announced_at": _normalize_datetime(self.announced_at_edit.get_datetime()),
            "file_number": self.file_number_edit.text().strip(),
            "notification_note": self.notification_note_edit.toPlainText().strip(),
            "planned_start_at": _normalize_datetime(
                self.planned_start_at_edit.get_datetime()
            ),
            "planned_start_place": self.planned_start_place_edit.text().strip(),
            "planned_control_place": self.planned_control_place_edit.text().strip(),
            "started_at": _normalize_datetime(self.started_at_edit.get_datetime()),
            "ended_at": _normalize_datetime(self.ended_at_edit.get_datetime()),
            "trade_union_notified_at": _normalize_datetime(
                self.trade_union_notified_at_edit.get_datetime()
            ),
            "management_notified_at": _normalize_datetime(
                self.management_notified_at_edit.get_datetime()
            ),
            "power_of_attorney_required": self.power_of_attorney_checkbox.isChecked(),
            "power_of_attorney_note": self.power_of_attorney_note_edit.toPlainText().strip(),
        }

    def get_snapshot(self) -> tuple:
        data = self.get_data()
        return tuple(data[key] for key in _EDITOR_FIELDS)

    def _validation_message(self, data: dict) -> str | None:
        if not data["authority_name"]:
            return AUTHORITY_REQUIRED_MESSAGE
        started = data["started_at"]
        ended = data["ended_at"]
        if started is not None and ended is not None and ended < started:
            return ENDED_BEFORE_STARTED_MESSAGE
        return None

    def _persist(self) -> bool:
        data = self.get_data()
        message = self._validation_message(data)
        if message:
            QMessageBox.warning(self, self.windowTitle(), message)
            return False
        payload = {key: data[key] for key in _EDITOR_FIELDS}
        try:
            if self._supervision_id is None:
                record = state_supervision_service.create_supervision(**payload)
            else:
                record = state_supervision_service.update_supervision(
                    int(self._supervision_id),
                    **payload,
                )
            loaded = state_supervision_service.get_supervision(int(record.id))
            if loaded is None:
                raise StateSupervisionError(SAVE_ERROR_MESSAGE)
            self._apply_record(loaded)
            self._persisted = True
            self.setWindowTitle(DIALOG_TITLE_EDIT)
            return True
        except StateSupervisionError as error:
            logger.exception("Uložení kontroly státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        except Exception:
            logger.exception("Uložení kontroly státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), SAVE_ERROR_MESSAGE)
            return False

    def _save_and_close(self) -> None:
        if not self._editor._run_save():
            return
        self.accept()
