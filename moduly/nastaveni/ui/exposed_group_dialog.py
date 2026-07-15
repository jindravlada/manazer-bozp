from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)


class ExposedGroupDialog(QDialog):
    def __init__(self, parent=None, group=None):
        super().__init__(parent)

        self.setWindowTitle("Ohrožená skupina osob")
        configure_resizable_form_dialog(self, width=520, height=360, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 9999)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název:", self.name)
        form.addRow("Poznámka:", self.note)
        form.addRow("Pořadí:", self.sort_order)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if group is not None:
            self.name.setText(group.name)
            self.note.setPlainText(group.note or "")
            self.sort_order.setValue(group.sort_order)
            self.active_checkbox.setChecked(group.active)

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "note": self.note.toPlainText().strip(),
            "sort_order": self.sort_order.value(),
            "active": self.active_checkbox.isChecked(),
        }
