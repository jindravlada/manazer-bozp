"""Výběr výsledku kontroly kontrolního bodu — sdílený widget."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
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


class ControlResultSelectorWidget(QWidget):
    result_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._entity_type = ""
        self._entity_id: int | None = None
        self._context: ControlPointContext | None = None
        self._must_be_saved_message = "Záznam je nutné nejdříve uložit."
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 4, 0, 0)
        layout.setSpacing(4)

        header = QLabel("Výsledek kontroly")
        header.setObjectName("InfoText")
        layout.addWidget(header)

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
        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("nepovinná")
        self._note_edit.editingFinished.connect(self._on_note_finished)
        note_row.addWidget(self._note_edit)
        layout.addLayout(note_row)

        self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)

    def configure(
        self,
        *,
        entity_type: str,
        entity_id: int | None,
        context: ControlPointContext,
        must_be_saved_message: str,
    ) -> None:
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._context = context
        self._must_be_saved_message = must_be_saved_message
        self._reload_from_storage()

    def current_result(self) -> str:
        for value, radio in self._radios.items():
            if radio.isChecked():
                return value
        return CONTROL_RESULT_NEKONTROLOVANO

    def _reload_from_storage(self) -> None:
        self._loading = True
        note_blocked = self._note_edit.blockSignals(True)
        try:
            if self._entity_id is None or self._context is None:
                self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)
                self._note_edit.clear()
                self.setEnabled(True)
                for radio in self._radios.values():
                    radio.setEnabled(self._entity_id is not None)
                self._note_edit.setEnabled(self._entity_id is not None)
                return

            row = control_result_service.get_for_control_point(
                self._entity_type,
                self._entity_id,
                self._context,
            )
            if row is None:
                self._set_result_ui(CONTROL_RESULT_NEKONTROLOVANO)
                self._note_edit.clear()
            else:
                self._set_result_ui(row.result)
                self._note_edit.setText(row.note or "")

            self.setEnabled(True)
            for radio in self._radios.values():
                radio.setEnabled(True)
            self._note_edit.setEnabled(True)
        finally:
            self._note_edit.blockSignals(note_blocked)
            self._loading = False

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

    def _on_radio_toggled(self, value: str, checked: bool) -> None:
        if not checked or self._loading:
            return

        if self._entity_id is None or self._context is None:
            QMessageBox.information(self, "Výsledek kontroly", self._must_be_saved_message)
            self._reload_from_storage()
            return

        previous = control_result_service.current_result(
            self._entity_type,
            self._entity_id,
            self._context,
        )
        if previous == value:
            return

        control_result_service.set_result(
            self._entity_type,
            self._entity_id,
            self._context,
            result=value,
            note=self._note_edit.text(),
        )
        self.result_changed.emit(value)

    def _on_note_finished(self) -> None:
        if self._loading or self._entity_id is None or self._context is None:
            return

        control_result_service.set_result(
            self._entity_type,
            self._entity_id,
            self._context,
            result=self.current_result(),
            note=self._note_edit.text(),
        )
