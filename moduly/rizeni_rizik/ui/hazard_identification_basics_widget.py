from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.rizeni_rizik.constants import (
    HAZARD_IDENTIFICATION_STATUSES,
    HAZARD_IDENTIFICATION_STATUS_LABELS,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import hazard_identification_service


class HazardIdentificationBasicsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.identification_number_label = QLabel("—")
        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()
        self.responsible_person = ThpWorkerSelector(
            include_empty=True,
            allow_custom_value=False,
        )
        self.started_at = NullableDateEdit()
        self.status = QComboBox()
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(90)

        for status in HAZARD_IDENTIFICATION_STATUSES:
            self.status.addItem(HAZARD_IDENTIFICATION_STATUS_LABELS[status], status)

        form.addRow("Číslo identifikace:", self.identification_number_label)
        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště *:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        form.addRow("Odpovědná osoba:", self.responsible_person)
        form.addRow("Datum zahájení:", self.started_at)
        form.addRow("Stav:", self.status)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        layout.addStretch()

        self.operation.currentIndexChanged.connect(self._on_operation_changed)
        self.workplace.currentIndexChanged.connect(self._on_workplace_changed)

        self._reload_operations()
        self._reset_workplaces()
        self._reset_workplace_parts()

    def load_identification(self, identification) -> None:
        self._reload_operations(preserve_id=identification.operation_id if identification else None)
        self._reload_workplaces(
            self.operation.currentData(),
            preserve_id=identification.workplace_id if identification else None,
        )
        self._reload_workplace_parts(
            self.workplace.currentData(),
            preserve_id=identification.workplace_part_id if identification else None,
        )

        if identification is None:
            self.identification_number_label.setText("—")
            self.responsible_person.set_person_id(None)
            self.started_at.clear_date()
            self.status.setCurrentIndex(0)
            self.note.clear()
            return

        self.identification_number_label.setText(identification.identification_number)
        self._select_combo_value(self.operation, identification.operation_id)
        self._reload_workplaces(
            identification.operation_id,
            preserve_id=identification.workplace_id,
        )
        self._select_combo_value(self.workplace, identification.workplace_id)
        self._reload_workplace_parts(
            identification.workplace_id,
            preserve_id=identification.workplace_part_id,
        )
        self._select_combo_value(self.workplace_part, identification.workplace_part_id)
        self.responsible_person.set_person_id(identification.responsible_person_id)
        self.started_at.set_date_value(identification.started_at)
        self._select_combo_value(self.status, identification.status)
        self.note.setPlainText(identification.note or "")

    def get_data(self) -> dict:
        workplace_part_id = self.workplace_part.currentData()
        responsible_person_id = self.responsible_person.current_person_id()
        return {
            "operation_id": self.operation.currentData(),
            "workplace_id": self.workplace.currentData(),
            "workplace_part_id": workplace_part_id,
            "responsible_person_id": responsible_person_id,
            "started_at": self.started_at.get_date(),
            "status": self.status.currentData(),
            "note": self.note.toPlainText().strip(),
        }

    def _reload_operations(self, *, preserve_id: int | None = None) -> None:
        self._populate_workplace_combo(
            self.operation,
            hazard_identification_service.get_active_operations(include_inactive=True),
            preserve_id=preserve_id,
            required=True,
        )

    def _reload_workplaces(self, operation_id: int | None, *, preserve_id: int | None = None) -> None:
        workplaces = hazard_identification_service.get_workplaces_for_operation(
            operation_id,
            include_inactive=True,
        )
        self._populate_workplace_combo(
            self.workplace,
            workplaces,
            preserve_id=preserve_id,
            required=True,
        )
        self.workplace.setEnabled(operation_id is not None)

    def _reload_workplace_parts(
        self,
        workplace_id: int | None,
        *,
        preserve_id: int | None = None,
    ) -> None:
        parts = hazard_identification_service.get_workplace_parts_for_workplace(
            workplace_id,
            include_inactive=True,
        )
        self._populate_workplace_combo(
            self.workplace_part,
            parts,
            preserve_id=preserve_id,
            required=False,
        )
        self.workplace_part.setEnabled(workplace_id is not None)

    def _reset_workplaces(self) -> None:
        self._populate_workplace_combo(self.workplace, [], required=True)
        self.workplace.setEnabled(False)

    def _reset_workplace_parts(self) -> None:
        self._populate_workplace_combo(self.workplace_part, [], required=False)
        self.workplace_part.setEnabled(False)

    def _populate_workplace_combo(
        self,
        combo: QComboBox,
        items,
        *,
        preserve_id: int | None = None,
        required: bool,
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        if not required:
            combo.addItem("", None)
        for item in items:
            combo.addItem(item.name, item.id)
        if preserve_id is not None:
            self._select_combo_value(combo, preserve_id)
        elif required:
            combo.setCurrentIndex(-1)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    @staticmethod
    def _select_combo_value(combo: QComboBox, value) -> None:
        if value is None:
            if combo.count() > 0 and combo.itemData(0) is None:
                combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(-1)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else -1)

    def _on_operation_changed(self) -> None:
        operation_id = self.operation.currentData()
        self._reload_workplaces(operation_id)
        self._reload_workplace_parts(self.workplace.currentData())

    def _on_workplace_changed(self) -> None:
        self._reload_workplace_parts(self.workplace.currentData())

    def operation_workplace_ids(self) -> list[int]:
        return [
            self.workplace.itemData(index)
            for index in range(self.workplace.count())
            if self.workplace.itemData(index) is not None
        ]

    def workplace_part_ids(self) -> list[int]:
        return [
            self.workplace_part.itemData(index)
            for index in range(self.workplace_part.count())
            if self.workplace_part.itemData(index) is not None
        ]
