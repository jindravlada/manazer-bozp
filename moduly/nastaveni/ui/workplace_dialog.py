from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box


class WorkplaceDialog(QDialog):
    def __init__(self, parent=None, workplace=None):
        super().__init__(parent)

        self.setWindowTitle("Pracoviště")
        self.resize(460, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.address = QLineEdit()
        self.note = QLineEdit()

        form.addRow("Název:", self.name)
        form.addRow("Adresa:", self.address)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if workplace is not None:
            self.name.setText(workplace.name)
            self.address.setText(workplace.address)
            self.note.setText(workplace.note)

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "address": self.address.text().strip(),
            "note": self.note.text().strip(),
        }
