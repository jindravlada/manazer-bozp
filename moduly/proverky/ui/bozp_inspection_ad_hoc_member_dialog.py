from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.tymy.sluzby.team_catalog_service import team_catalog_service


class BozpInspectionAdHocMemberDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Přizvaná osoba")
        self.resize(540, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.person_source_combo = QComboBox()
        self.person_source_combo.addItem("THP pracovník", "thp")
        self.person_source_combo.addItem("Osoba ze seznamu", "person")
        self.person_source_combo.addItem("Ruční zadání", "manual")

        self.thp_selector = ThpWorkerSelector(include_empty=True)
        self.person_selector = PersonSelector(include_inactive=True, allow_add_new=True)
        self.manual_name_edit = QLineEdit()

        self.role_combo = QComboBox()
        for role in team_catalog_service.get_team_roles():
            self.role_combo.addItem(role.nazev, role.id)
        invited_index = self.role_combo.findData("prizvany_odbornik")
        if invited_index >= 0:
            self.role_combo.setCurrentIndex(invited_index)

        form.addRow("Zdroj osoby:", self.person_source_combo)
        form.addRow("THP pracovník:", self.thp_selector)
        form.addRow("Osoba:", self.person_selector)
        form.addRow("Jméno:", self.manual_name_edit)
        form.addRow("Role:", self.role_combo)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.person_source_combo.currentIndexChanged.connect(self._update_person_source)
        self._update_person_source()

    def _update_person_source(self) -> None:
        source = self.person_source_combo.currentData()
        self.thp_selector.setVisible(source == "thp")
        self.person_selector.setVisible(source == "person")
        self.manual_name_edit.setVisible(source == "manual")

    def get_data(self) -> dict:
        source = self.person_source_combo.currentData()
        role_id = self.role_combo.currentData()
        role_name = self.role_combo.currentText()

        if source == "thp":
            worker = self.thp_selector.current_person()
            return {
                "thp_worker_id": self.thp_selector.current_person_id(),
                "person_id": None,
                "person_name": worker.display_name if worker else self.thp_selector.currentText().strip(),
                "role_id": role_id,
                "role_name": role_name,
            }

        if source == "person":
            person = self.person_selector.current_person()
            return {
                "thp_worker_id": None,
                "person_id": self.person_selector.current_person_id(),
                "person_name": person.display_name if person else self.person_selector.display_text(),
                "role_id": role_id,
                "role_name": role_name,
            }

        return {
            "thp_worker_id": None,
            "person_id": None,
            "person_name": self.manual_name_edit.text().strip(),
            "role_id": role_id,
            "role_name": role_name,
        }
