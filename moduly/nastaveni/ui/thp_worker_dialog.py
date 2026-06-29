from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


class ThpWorkerDialog(QDialog):
    def __init__(self, parent=None, worker=None):
        super().__init__(parent)

        self.setWindowTitle("THP pracovník")
        self.resize(460, 340)

        layout = QFormLayout(self)

        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.position = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.performs_controls_checkbox = QCheckBox("Provádí kontroly")

        layout.addRow("Titul před:", self.title_before)
        layout.addRow("Jméno:", self.first_name)
        layout.addRow("Příjmení:", self.last_name)
        layout.addRow("Titul za:", self.title_after)
        layout.addRow("Funkce:", self.position)
        layout.addRow("Telefon:", self.phone)
        layout.addRow("E-mail:", self.email)
        layout.addRow("", self.performs_controls_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if worker is not None:
            self.title_before.setText(worker.title_before)
            self.first_name.setText(worker.first_name)
            self.last_name.setText(worker.last_name)
            self.title_after.setText(worker.title_after)
            self.position.setText(worker.position)
            self.phone.setText(worker.phone)
            self.email.setText(worker.email)
            self.performs_controls_checkbox.setChecked(worker.performs_controls)

    def get_data(self) -> dict:
        return {
            "title_before": self.title_before.text().strip(),
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "title_after": self.title_after.text().strip(),
            "position": self.position.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "performs_controls": self.performs_controls_checkbox.isChecked(),
        }
