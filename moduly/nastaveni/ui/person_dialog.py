from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import apply_save_cancel_labels, configure_resizable_form_dialog, wrap_in_scroll_area


class PersonDialog(QDialog):
    def __init__(self, parent=None, person=None):
        super().__init__(parent)

        self.setWindowTitle("Osoba")
        configure_resizable_form_dialog(self, width=520, height=460, min_width=420, min_height=360)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.organization = QLineEdit()
        self.job_title = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)
        self.is_employee_checkbox = QCheckBox("Zaměstnanec")

        form.addRow("Titul před:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za:", self.title_after)
        form.addRow("Organizace:", self.organization)
        form.addRow("Pracovní zařazení:", self.job_title)
        form.addRow("E-mail:", self.email)
        form.addRow("Telefon:", self.phone)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.is_employee_checkbox)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        apply_save_cancel_labels(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if person is not None:
            self.title_before.setText(person.title_before or "")
            self.first_name.setText(person.first_name or "")
            self.last_name.setText(person.last_name or "")
            self.title_after.setText(person.title_after or "")
            self.organization.setText(person.organization or "")
            self.job_title.setText(person.job_title or "")
            self.email.setText(person.email or "")
            self.phone.setText(person.phone or "")
            self.note.setPlainText(person.note or "")
            self.is_employee_checkbox.setChecked(person.is_employee)
            self.active_checkbox.setChecked(person.active)

    def get_data(self) -> dict:
        return {
            "title_before": self.title_before.text().strip(),
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "title_after": self.title_after.text().strip(),
            "organization": self.organization.text().strip(),
            "job_title": self.job_title.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
            "is_employee": self.is_employee_checkbox.isChecked(),
        }
