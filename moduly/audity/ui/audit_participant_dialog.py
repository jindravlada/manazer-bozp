from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class AuditParticipantDialog(QDialog):
    def __init__(self, parent=None, participant=None):
        super().__init__(parent)

        self.setWindowTitle("Účastník auditu")
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.role_edit = QLineEdit()
        self.organization_edit = QLineEdit()

        self.name_edit.setPlaceholderText("Jméno účastníka")
        self.role_edit.setPlaceholderText("Funkce nebo role")
        self.organization_edit.setPlaceholderText("Organizace")

        form.addRow("Jméno:", self.name_edit)
        form.addRow("Funkce:", self.role_edit)
        form.addRow("Organizace:", self.organization_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if participant is not None:
            self.name_edit.setText(participant.name or "")
            self.role_edit.setText(participant.role or "")
            self.organization_edit.setText(participant.organization or "")

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "role": self.role_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
        }
