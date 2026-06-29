from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.person_selector import PersonSelector


class AuditParticipantDialog(QDialog):
    def __init__(self, parent=None, participant=None):
        super().__init__(parent)

        self.setWindowTitle("Účastník auditu")
        self.resize(520, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.person_selector = PersonSelector(include_inactive=True)
        self.role_edit = QLineEdit()
        self.organization_edit = QLineEdit()

        self.role_edit.setPlaceholderText("Funkce nebo role")
        self.organization_edit.setPlaceholderText("Organizace")

        form.addRow("Jméno:", self.person_selector)
        form.addRow("Funkce:", self.role_edit)
        form.addRow("Organizace:", self.organization_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._loading = False
        self.person_selector.activated.connect(self._prefill_from_person)

        if participant is not None:
            self._loading = True
            if participant.person_id:
                self.person_selector.set_person_id(participant.person_id)
            elif participant.name:
                self.person_selector.setCurrentText(participant.name)
            self.role_edit.setText(participant.role or "")
            self.organization_edit.setText(participant.organization or "")
            self._loading = False

    def _prefill_from_person(self, index: int) -> None:
        if self._loading:
            return

        person = self.person_selector.current_person()
        if person and person.organization:
            self.organization_edit.setText(person.organization)

    def get_data(self) -> dict:
        person = self.person_selector.current_person()
        person_id = self.person_selector.current_person_id()
        name = person.display_name if person else self.person_selector.display_text()

        return {
            "person_id": person_id,
            "name": name,
            "role": self.role_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
        }
