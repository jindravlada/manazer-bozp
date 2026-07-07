from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box
from moduly.pravni_pozadavky.constants import DEFAULT_SANCTION_CURRENCY


class LegalRequirementSanctionDialog(QDialog):
    def __init__(self, parent=None, sanction=None):
        super().__init__(parent)
        self.sanction = sanction

        self.setWindowTitle("Sankce" if sanction is None else "Upravit sankci")
        configure_resizable_form_dialog(self, width=620, height=420, min_width=480, min_height=320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.authority = QLineEdit()
        self.legal_reference = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(90)
        self.max_amount = QLineEdit()
        self.max_amount.setPlaceholderText("Volitelné")
        self.currency = QLineEdit()
        self.currency.setText(DEFAULT_SANCTION_CURRENCY)
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Orgán:", self.authority)
        form.addRow("Právní odkaz:", self.legal_reference)
        form.addRow("Popis:", self.description)
        form.addRow("Horní hranice pokuty:", self.max_amount)
        form.addRow("Měna:", self.currency)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        layout.addWidget(create_save_cancel_box(self))

        if sanction is not None:
            self._load_sanction(sanction)

    def _load_sanction(self, sanction) -> None:
        self.authority.setText(sanction.authority)
        self.legal_reference.setText(sanction.legal_reference)
        self.description.setPlainText(sanction.description)
        if sanction.max_amount is not None:
            self.max_amount.setText(str(sanction.max_amount).replace(".", ","))
        self.currency.setText(sanction.currency or DEFAULT_SANCTION_CURRENCY)
        self.note.setPlainText(sanction.note)

    def get_data(self) -> dict:
        return {
            "authority": self.authority.text().strip(),
            "legal_reference": self.legal_reference.text().strip(),
            "description": self.description.toPlainText().strip(),
            "max_amount": self.max_amount.text().strip() or None,
            "currency": self.currency.text().strip(),
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        if not self.description.toPlainText().strip():
            QMessageBox.warning(self, "Sankce", "Popis sankce je povinný.")
            return
        super().accept()
