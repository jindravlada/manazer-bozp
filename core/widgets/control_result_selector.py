"""Výběr výsledku kontroly kontrolního bodu — sdílený widget."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import CONTROL_RESULT_NEKONTROLOVANO
from core.shared.control_result_display import CONTROL_RESULT_OPTIONS
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service

SHARED_EXPERIENCE_LABEL = "Sdílet jako zkušenost"


class ControlResultSelectorWidget(QWidget):
    result_changed = Signal(str)
    data_saved = Signal()

    def __init__(self, parent=None, *, auto_persist: bool = True, deferred_edits=None):
        super().__init__(parent)

        self._entity_type = ""
        self._entity_id: int | None = None
        self._context: ControlPointContext | None = None
        self._must_be_saved_message = "Záznam je nutné nejdříve uložit."
        self._loading = False
        self._auto_persist = auto_persist
        self._deferred_edits = deferred_edits

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 0, 0)
        layout.setSpacing(4)

        header = QLabel("Výsledek kontroly")
        header.setObjectName("InfoText")
        layout.addWidget(header)
        self._result_header = header

        self._button_group = QButtonGroup(self)
        self._radios: dict[str, QRadioButton] = {}

        for value, label in CONTROL_RESULT_OPTIONS:
            radio = QRadioButton(label)
            radio.toggled.connect(lambda checked, v=value: self._on_radio_toggled(v, checked))
            self._button_group.addButton(radio)
            self._radios[value] = radio
            layout.addWidget(radio)

        note_row = QHBoxLayout()
        note_row.setContentsMargins(0, 0, 0, 0)
        note_row.addWidget(QLabel("Poznámka:"))
        self._note_label = note_row.itemAt(0).widget()
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("nepovinná")
        self._note_edit.editingFinished.connect(self._on_note_finished)
        self._note_edit.textChanged.connect(self._on_note_text_changed)
        note_row.addWidget(self._note_edit)
        layout.addLayout(note_row)
        self._note_row_widgets = (self._note_label, self._note_edit)

        self._shared_experience_check = QCheckBox(SHARED_EXPERIENCE_LABEL)
        self._shared_experience_check.toggled.connect(self._on_shared_experience_toggled)
        layout.addWidget(self._shared_experience_check)

        self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)

    def configure(
        self,
        *,
        entity_type: str,
        entity_id: int | None,
        context: ControlPointContext,
        must_be_saved_message: str,
        result_header: str = "Výsledek kontroly",
        note_label: str = "Poznámka:",
        show_note: bool = True,
    ) -> None:
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._context = context
        self._must_be_saved_message = must_be_saved_message
        self._result_header.setText(result_header)
        self._note_label.setText(note_label)
        for widget in self._note_row_widgets:
            widget.setVisible(bool(show_note))
        self._reload_from_storage()

    def current_result(self) -> str:
        for value, radio in self._radios.items():
            if radio.isChecked():
                return value
        return CONTROL_RESULT_NEKONTROLOVANO

    def _reload_from_storage(self) -> None:
        self._loading = True
        note_blocked = self._note_edit.blockSignals(True)
        shared_blocked = self._shared_experience_check.blockSignals(True)
        try:
            if self._entity_id is None or self._context is None:
                self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)
                self._note_edit.clear()
                self._shared_experience_check.setChecked(False)
                self._set_enabled(False)
                return

            row = self._load_row()
            if row is None:
                self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)
                self._note_edit.clear()
                self._shared_experience_check.setChecked(False)
            else:
                self._set_result_ui(row.result)
                self._note_edit.setText(row.note or "")
                self._shared_experience_check.setChecked(bool(row.shared_experience))

            self._set_enabled(True)
        finally:
            self._note_edit.blockSignals(note_blocked)
            self._shared_experience_check.blockSignals(shared_blocked)
            self._loading = False

    def _load_row(self):
        if self._entity_id is None or self._context is None:
            return None
        if self._deferred_edits is not None and not self._auto_persist:
            return self._deferred_edits.get_control_result_view(
                self._entity_type,
                self._entity_id,
                self._context,
            )
        return control_result_service.get_for_control_point(
            self._entity_type,
            self._entity_id,
            self._context,
        )

    def _current_stored_result(self) -> str:
        if self._entity_id is None or self._context is None:
            return CONTROL_RESULT_NEKONTROLOVANO
        if self._deferred_edits is not None and not self._auto_persist:
            return self._deferred_edits.current_result(
                self._entity_type,
                self._entity_id,
                self._context,
            )
        return control_result_service.current_result(
            self._entity_type,
            self._entity_id,
            self._context,
        )

    def _set_enabled(self, enabled: bool) -> None:
        self.setEnabled(True)
        for radio in self._radios.values():
            radio.setEnabled(enabled)
        self._note_edit.setEnabled(enabled)
        self._shared_experience_check.setEnabled(enabled)

    def _set_result_ui(self, result: str) -> None:
        radio = self._radios.get(result)
        if radio is None:
            return

        blocked = {item: item.blockSignals(True) for item in self._radios.values()}
        try:
            radio.setChecked(True)
        finally:
            for item, previous in blocked.items():
                item.blockSignals(previous)

    def _save_current_state(self, *, emit_result_changed: bool = False) -> None:
        if self._entity_id is None or self._context is None:
            return

        if self._deferred_edits is not None and not self._auto_persist:
            self._deferred_edits.set_control_result(
                self._entity_type,
                self._entity_id,
                self._context,
                result=self.current_result(),
                note=self._note_edit.text(),
                shared_experience=self._shared_experience_check.isChecked(),
            )
        else:
            control_result_service.set_result(
                self._entity_type,
                self._entity_id,
                self._context,
                result=self.current_result(),
                note=self._note_edit.text(),
                shared_experience=self._shared_experience_check.isChecked(),
            )
        if emit_result_changed:
            self.result_changed.emit(self.current_result())
        self.data_saved.emit()

    def _on_radio_toggled(self, value: str, checked: bool) -> None:
        if not checked or self._loading:
            return

        if self._entity_id is None or self._context is None:
            QMessageBox.information(self, "Výsledek kontroly", self._must_be_saved_message)
            self._reload_from_storage()
            return

        previous = self._current_stored_result()
        if previous == value:
            return

        self._save_current_state(emit_result_changed=True)

    def _on_note_finished(self) -> None:
        if self._loading or self._entity_id is None or self._context is None:
            return
        # Při auto_persist ukládat na opuštění pole; deferred řeší textChanged.
        if self._deferred_edits is not None and not self._auto_persist:
            return
        self._save_current_state()

    def _on_note_text_changed(self, _text: str) -> None:
        if self._loading or self._entity_id is None or self._context is None:
            return
        if self._deferred_edits is None or self._auto_persist:
            return
        self._save_current_state()

    def _on_shared_experience_toggled(self, _checked: bool) -> None:
        if self._loading or self._entity_id is None or self._context is None:
            return

        self._save_current_state()
