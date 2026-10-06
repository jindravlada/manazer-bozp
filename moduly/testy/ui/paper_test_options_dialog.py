"""Volba, zda se spolu s písemným testem vytvoří i klíč."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QVBoxLayout

from moduly.testy.constants import PAPER_TEST_KEY_OPTION


class PaperTestOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Písemný test")
        layout = QVBoxLayout(self)
        self.key_checkbox = QCheckBox(PAPER_TEST_KEY_OPTION)
        self.key_checkbox.setObjectName("paper-test-key-checkbox")
        self.key_checkbox.setChecked(False)
        layout.addWidget(self.key_checkbox)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Vytvořit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def include_key(self) -> bool:
        return self.key_checkbox.isChecked()
