from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


class WorkplaceDialog(QDialog):
    def __init__(self, parent=None, workplace=None):
        super().__init__(parent)

        self.setWindowTitle("Pracoviště")
        self.resize(460, 240)

        layout = QFormLayout(self)

        self.name = QLineEdit()
        self.address = QLineEdit()
        self.note = QLineEdit()

        layout.addRow("Název:", self.name)
        layout.addRow("Adresa:", self.address)
        layout.addRow("Poznámka:", self.note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

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
