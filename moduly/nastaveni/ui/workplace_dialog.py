from PySide6.QtWidgets import (
    QCheckBox,
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
from moduly.nastaveni.sluzby.workplace_audit_planning import (
    dump_preferred_months,
    parse_preferred_months_json,
)


class WorkplaceDialog(QDialog):
    def __init__(self, parent=None, workplace=None):
        super().__init__(parent)

        self.setWindowTitle("Pracoviště")
        self.resize(520, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.address = QLineEdit()
        self.note = QLineEdit()
        self.audit_enabled = QCheckBox("Auditovat")
        self.audit_interval = QSpinBox()
        self.audit_interval.setRange(1, 60)
        self.audit_interval.setSuffix(" měsíců")

        form.addRow("Název:", self.name)
        form.addRow("Adresa:", self.address)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.audit_enabled)
        form.addRow("Auditní interval:", self.audit_interval)

        layout.addLayout(form)

        months_group = QGroupBox("Preferované měsíce")
        months_layout = QGridLayout(months_group)
        self.month_checkboxes: list[QCheckBox] = []
        for index, month_name in enumerate(PLANNED_MONTH_NAMES, start=1):
            checkbox = QCheckBox(month_name)
            self.month_checkboxes.append(checkbox)
            row = (index - 1) // 3
            column = (index - 1) % 3
            months_layout.addWidget(checkbox, row, column)
        layout.addWidget(months_group)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if workplace is not None:
            self.name.setText(workplace.name)
            self.address.setText(workplace.address)
            self.note.setText(workplace.note)
            self.audit_enabled.setChecked(bool(workplace.audit_enabled))
            self.audit_interval.setValue(int(workplace.audit_interval_months))
            preferred = set(parse_preferred_months_json(workplace.preferred_months_json))
            for index, checkbox in enumerate(self.month_checkboxes, start=1):
                checkbox.setChecked(index in preferred)
        else:
            self.audit_enabled.setChecked(DEFAULT_WORKPLACE_AUDIT_ENABLED)
            self.audit_interval.setValue(DEFAULT_WORKPLACE_AUDIT_INTERVAL_MONTHS)
            for index, checkbox in enumerate(self.month_checkboxes, start=1):
                checkbox.setChecked(index in DEFAULT_PREFERRED_AUDIT_MONTHS)

    def get_data(self) -> dict:
        preferred_months = [
            index
            for index, checkbox in enumerate(self.month_checkboxes, start=1)
            if checkbox.isChecked()
        ]
        return {
            "name": self.name.text().strip(),
            "address": self.address.text().strip(),
            "note": self.note.text().strip(),
            "audit_enabled": self.audit_enabled.isChecked(),
            "audit_interval_months": self.audit_interval.value(),
            "preferred_months_json": dump_preferred_months(preferred_months),
        }
