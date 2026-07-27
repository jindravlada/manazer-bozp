from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)


class ResponsibilityRoleDialog(QDialog):
    def __init__(self, parent=None, role=None):
        super().__init__(parent)

        self.setWindowTitle("Funkce / role")
        configure_resizable_form_dialog(self, width=520, height=360, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(90)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=role is None)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if role is not None:
            self.name.setText(role.name)
            self.description.setPlainText(role.description or "")
            self.active_checkbox.setChecked(role.active)

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
