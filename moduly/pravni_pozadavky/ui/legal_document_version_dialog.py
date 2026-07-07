from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit


class LegalDocumentVersionDialog(QDialog):
    def __init__(self, parent=None, version=None):
        super().__init__(parent)
        self.version = version

        self.setWindowTitle("Verze předpisu" if version is None else "Upravit verzi")
        configure_resizable_form_dialog(self, width=640, height=480, min_width=480, min_height=360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.version_name = QLineEdit()
        self.valid_from = NullableDateEdit()
        self.valid_to = NullableDateEdit()
        self.effective_from = NullableDateEdit()
        self.effective_to = NullableDateEdit()
        self.publication_date = NullableDateEdit()
        self.source_url = QLineEdit()
        self.local_file_path = QLineEdit()
        self.checksum = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Název verze:", self.version_name)
        form.addRow("Platnost od:", self.valid_from)
        form.addRow("Platnost do:", self.valid_to)
        form.addRow("Účinnost od:", self.effective_from)
        form.addRow("Účinnost do:", self.effective_to)
        form.addRow("Datum publikace:", self.publication_date)
        form.addRow("Zdroj URL:", self.source_url)
        form.addRow("Lokální soubor:", self.local_file_path)
        form.addRow("Checksum:", self.checksum)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        layout.addWidget(create_save_cancel_box(self))

        if version is not None:
            self._load_version(version)

    def _load_version(self, version) -> None:
        self.version_name.setText(version.version_name)
        self.valid_from.set_date_value(version.valid_from)
        self.valid_to.set_date_value(version.valid_to)
        self.effective_from.set_date_value(version.effective_from)
        self.effective_to.set_date_value(version.effective_to)
        self.publication_date.set_date_value(version.publication_date)
        self.source_url.setText(version.source_url)
        self.local_file_path.setText(version.local_file_path)
        self.checksum.setText(version.checksum)
        self.note.setPlainText(version.note)

    def get_data(self) -> dict:
        return {
            "version_name": self.version_name.text().strip(),
            "valid_from": self.valid_from.get_date(),
            "valid_to": self.valid_to.get_date(),
            "effective_from": self.effective_from.get_date(),
            "effective_to": self.effective_to.get_date(),
            "publication_date": self.publication_date.get_date(),
            "source_url": self.source_url.text().strip(),
            "local_file_path": self.local_file_path.text().strip(),
            "checksum": self.checksum.text().strip(),
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        if not self.version_name.text().strip():
            QMessageBox.warning(self, "Verze předpisu", "Název verze je povinný.")
            return
        super().accept()
