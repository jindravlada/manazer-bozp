from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.tymy.modely.team import Team
from moduly.tymy.sluzby.team_catalog_service import team_catalog_service


class TeamDialog(QDialog):
    def __init__(self, parent=None, team: Team | None = None):
        super().__init__(parent)

        self.setWindowTitle("Tým")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(90)

        self.team_type_combo = QComboBox()
        for team_type in team_catalog_service.get_team_types():
            self.team_type_combo.addItem(team_type.nazev, team_type.id)

        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        self.valid_from_edit = DateEdit()
        self.valid_to_edit = NullableDateEdit()

        form.addRow("Název:", self.name_edit)
        form.addRow("Popis:", self.description_edit)
        form.addRow("Typ týmu:", self.team_type_combo)
        form.addRow("", self.active_checkbox)
        form.addRow("Platnost od:", self.valid_from_edit)
        form.addRow("Platnost do:", self.valid_to_edit)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if team is not None:
            self.name_edit.setText(team.name)
            self.description_edit.setPlainText(team.description or "")
            type_index = self.team_type_combo.findData(team.team_type_id)
            if type_index >= 0:
                self.team_type_combo.setCurrentIndex(type_index)
            self.active_checkbox.setChecked(team.active)
            if team.valid_from:
                self.valid_from_edit.set_date_iso(team.valid_from.isoformat())
            if team.valid_to:
                self.valid_to_edit.set_date_iso(team.valid_to.isoformat())

    def get_data(self) -> dict:
        valid_from = self.valid_from_edit.date().toPython()
        valid_to = self.valid_to_edit.get_date()

        return {
            "name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "team_type_id": self.team_type_combo.currentData(),
            "active": self.active_checkbox.isChecked(),
            "valid_from": valid_from if isinstance(valid_from, date) else date.today(),
            "valid_to": valid_to,
        }
