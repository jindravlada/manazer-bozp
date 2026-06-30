from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box


class ThpWorkerDialog(QDialog):
    def __init__(self, parent=None, worker=None):
        super().__init__(parent)

        self.setWindowTitle("THP pracovník")
        self.resize(460, 340)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.position = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.performs_controls_checkbox = QCheckBox("Provádí kontroly")

        form.addRow("Titul před:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za:", self.title_after)
        form.addRow("Funkce:", self.position)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("", self.performs_controls_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
