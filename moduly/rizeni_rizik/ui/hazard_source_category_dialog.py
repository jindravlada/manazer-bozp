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


class HazardSourceCategoryDialog(QDialog):
    def __init__(self, parent=None, category=None):
        super().__init__(parent)

        self.setWindowTitle("Kategorie zdroje rizika")
        configure_resizable_form_dialog(self, width=520, height=400, min_width=420, min_height=300)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(90)
        self.sort_order = QSpinBox()
        self.sort_order.setRange(0, 9999)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("Pořadí:", self.sort_order)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if category is not None:
            self.name.setText(category.name)
            self.description.setPlainText(category.description or "")
            self.sort_order.setValue(category.sort_order)
            self.active_checkbox.setChecked(bool(category.active))

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "sort_order": self.sort_order.value(),
            "active": self.active_checkbox.isChecked(),
        }
