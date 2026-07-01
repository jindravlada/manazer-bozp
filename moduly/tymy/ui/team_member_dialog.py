from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QStackedWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.tymy.modely.team_member import TeamMember
from moduly.tymy.sluzby.team_catalog_service import team_catalog_service


class TeamMemberDialog(QDialog):
    def __init__(self, parent=None, member: TeamMember | None = None):
        super().__init__(parent)

        self.setWindowTitle("Člen týmu")
        self.resize(540, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.person_source_combo = QComboBox()
        self.person_source_combo.addItem("THP pracovník", "thp")
        self.person_source_combo.addItem("Osoba ze seznamu", "person")

        self.person_stack = QStackedWidget()
        self.thp_selector = ThpWorkerSelector(include_empty=True)
        self.person_selector = PersonSelector(include_inactive=True, allow_add_new=True)
        self.person_stack.addWidget(self.thp_selector)
        self.person_stack.addWidget(self.person_selector)

        self.role_combo = QComboBox()
        for role in team_catalog_service.get_team_roles():
            self.role_combo.addItem(role.nazev, role.id)

        self.mandatory_checkbox = QCheckBox("Povinný člen")

        form.addRow("Zdroj osoby:", self.person_source_combo)
        form.addRow("Osoba:", self.person_stack)
        form.addRow("Role:", self.role_combo)
        form.addRow("", self.mandatory_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.person_source_combo.currentIndexChanged.connect(self._update_person_source)
        self._update_person_source()

        if member is not None:
            if member.thp_worker_id is not None:
                self.person_source_combo.setCurrentIndex(
                    self.person_source_combo.findData("thp")
                )
                self.thp_selector.set_person_id(member.thp_worker_id)
            elif member.person_id is not None:
                self.person_source_combo.setCurrentIndex(
                    self.person_source_combo.findData("person")
                )
                self.person_selector.set_person_id(member.person_id)
            else:
                self.person_source_combo.setCurrentIndex(
                    self.person_source_combo.findData("person")
                )
                self.person_selector.setCurrentText(member.person_name or "")

            role_index = self.role_combo.findData(member.role_id)
            if role_index >= 0:
                self.role_combo.setCurrentIndex(role_index)
            self.mandatory_checkbox.setChecked(member.mandatory)

    def _update_person_source(self) -> None:
        use_thp = self.person_source_combo.currentData() == "thp"
        self.person_stack.setCurrentIndex(0 if use_thp else 1)

    def get_data(self) -> dict:
        use_thp = self.person_source_combo.currentData() == "thp"

        if use_thp:
            worker = self.thp_selector.current_person()
            thp_worker_id = self.thp_selector.current_person_id()
            person_name = worker.display_name if worker else self.thp_selector.currentText().strip()
            return {
                "thp_worker_id": thp_worker_id,
                "person_id": None,
                "person_name": person_name,
                "role_id": self.role_combo.currentData(),
                "mandatory": self.mandatory_checkbox.isChecked(),
            }

        person = self.person_selector.current_person()
        person_id = self.person_selector.current_person_id()
        person_name = person.display_name if person else self.person_selector.display_text()
        return {
            "thp_worker_id": None,
            "person_id": person_id,
            "person_name": person_name,
            "role_id": self.role_combo.currentData(),
            "mandatory": self.mandatory_checkbox.isChecked(),
        }
