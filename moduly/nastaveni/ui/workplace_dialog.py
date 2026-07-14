from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.constants import PLANNED_MONTH_NAMES
from moduly.nastaveni.constants.workplace_audit_constants import (
    DEFAULT_PREFERRED_AUDIT_MONTHS,
    DEFAULT_WORKPLACE_AUDIT_ENABLED,
    DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS,
)
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_LABELS,
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPES,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.nastaveni.sluzby.workplace_audit_planning import (
    dump_preferred_months,
    parse_preferred_months_json,
)


class WorkplaceDialog(QDialog):
    def __init__(
        self,
        parent=None,
        workplace=None,
        *,
        default_item_type: str | None = None,
        default_parent_id: int | None = None,
    ):
        super().__init__(parent)

        self._workplace_id = workplace.id if workplace is not None else None
        self._initial_parent_id = workplace.parent_id if workplace is not None else default_parent_id

        self.setWindowTitle("Provozy a pracoviště")
        self.resize(560, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.item_type = QComboBox()
        for item_type in WORKPLACE_ITEM_TYPES:
            self.item_type.addItem(WORKPLACE_ITEM_TYPE_LABELS[item_type], item_type)

        self.parent_item = QComboBox()
        self.parent_item.setPlaceholderText("—")

        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        self.note = QLineEdit()
        self.address = QLineEdit()
        self.audit_enabled = QCheckBox("Auditovat")
        self.audit_interval = QSpinBox()
        self.audit_interval.setRange(1, 60)
        self.audit_interval.setSuffix(" měsíců")

        form.addRow("Název:", self.name)
        form.addRow("Typ:", self.item_type)
        form.addRow("Nadřazená položka:", self.parent_item)
        form.addRow("", self.active_checkbox)
        form.addRow("Poznámka:", self.note)
        form.addRow("Adresa:", self.address)
        form.addRow("", self.audit_enabled)
        form.addRow("Auditní interval:", self.audit_interval)

        layout.addLayout(form)

        self.audit_group = QGroupBox("Preferované měsíce")
        months_layout = QGridLayout(self.audit_group)
        self.month_checkboxes: list[QCheckBox] = []
        for index, month_name in enumerate(PLANNED_MONTH_NAMES, start=1):
            checkbox = QCheckBox(month_name)
            self.month_checkboxes.append(checkbox)
            row = (index - 1) // 3
            column = (index - 1) % 3
            months_layout.addWidget(checkbox, row, column)
        layout.addWidget(self.audit_group)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.item_type.currentIndexChanged.connect(self._on_item_type_changed)

        if workplace is not None:
            self.name.setText(workplace.name)
            self.note.setText(workplace.note)
            self.address.setText(workplace.address)
            self.active_checkbox.setChecked(bool(workplace.active))
            self.audit_enabled.setChecked(bool(workplace.audit_enabled))
            self.audit_interval.setValue(int(workplace.audit_interval_months))
            preferred = set(parse_preferred_months_json(workplace.preferred_months_json))
            for index, checkbox in enumerate(self.month_checkboxes, start=1):
                checkbox.setChecked(index in preferred)
            self._set_item_type(workplace.item_type)
        else:
            self.audit_enabled.setChecked(DEFAULT_WORKPLACE_AUDIT_ENABLED)
            self.audit_interval.setValue(DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS)
            for index, checkbox in enumerate(self.month_checkboxes, start=1):
                checkbox.setChecked(index in DEFAULT_PREFERRED_AUDIT_MONTHS)
            self._set_item_type(default_item_type or WORKPLACE_ITEM_TYPE_OPERATION)

        self._refresh_parent_candidates()
        if self._initial_parent_id is not None:
            self._select_parent(self._initial_parent_id)

    def _set_item_type(self, item_type: str) -> None:
        index = self.item_type.findData(item_type)
        if index >= 0:
            self.item_type.setCurrentIndex(index)

    def _select_parent(self, parent_id: int | None) -> None:
        if parent_id is None:
            self.parent_item.setCurrentIndex(-1)
            return
        for index in range(self.parent_item.count()):
            if self.parent_item.itemData(index) == parent_id:
                self.parent_item.setCurrentIndex(index)
                return

    def _on_item_type_changed(self) -> None:
        self._refresh_parent_candidates()
        self._update_operation_fields_visibility()

    def _refresh_parent_candidates(self) -> None:
        item_type = self.item_type.currentData()
        current_parent_id = self.parent_item.currentData()
        if current_parent_id is None and self._initial_parent_id is not None:
            current_parent_id = self._initial_parent_id

        self.parent_item.blockSignals(True)
        self.parent_item.clear()
        candidates = settings_service.get_workplace_parent_candidates(
            item_type=item_type,
            current_id=self._workplace_id,
            active_only=True,
        )
        for candidate in candidates:
            label = f"{candidate.name} ({settings_service.workplace_item_type_label(candidate.item_type)})"
            self.parent_item.addItem(label, candidate.id)

        if item_type == WORKPLACE_ITEM_TYPE_OPERATION:
            self.parent_item.setEnabled(False)
            self.parent_item.setCurrentIndex(-1)
        else:
            self.parent_item.setEnabled(True)
            self._select_parent(current_parent_id)

        self.parent_item.blockSignals(False)
        self._update_operation_fields_visibility()

    def _update_operation_fields_visibility(self) -> None:
        is_operation = self.item_type.currentData() == WORKPLACE_ITEM_TYPE_OPERATION
        for widget in (
            self.address,
            self.audit_enabled,
            self.audit_interval,
            self.audit_group,
        ):
            widget.setVisible(is_operation)
            widget.setEnabled(is_operation)

    def get_data(self) -> dict:
        preferred_months = [
            index
            for index, checkbox in enumerate(self.month_checkboxes, start=1)
            if checkbox.isChecked()
        ]
        item_type = self.item_type.currentData()
        parent_id = None
        if item_type != WORKPLACE_ITEM_TYPE_OPERATION and self.parent_item.isEnabled():
            parent_id = self.parent_item.currentData()

        data = {
            "name": self.name.text().strip(),
            "item_type": item_type,
            "parent_id": parent_id,
            "active": self.active_checkbox.isChecked(),
            "note": self.note.text().strip(),
        }
        if item_type == WORKPLACE_ITEM_TYPE_OPERATION:
            data.update(
                {
                    "address": self.address.text().strip(),
                    "audit_enabled": self.audit_enabled.isChecked(),
                    "audit_interval_months": self.audit_interval.value(),
                    "preferred_months_json": dump_preferred_months(preferred_months),
                }
            )
        return data
