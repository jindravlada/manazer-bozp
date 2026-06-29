from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.nullable_date_edit import NullableDateEdit


class MuChronologieEntryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        entry=None,
        *,
        title: str = "Událost v časové ose",
        default_date: date | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(520, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.datum_edit = NullableDateEdit()
        self.cas_edit = QLineEdit()
        self.cas_edit.setPlaceholderText("např. 14:35")
        self.typ_edit = QLineEdit()
        self.typ_edit.setPlaceholderText("např. Oznámení, Ohledání místa")
        self.popis_edit = QTextEdit()
        self.popis_edit.setPlaceholderText("Stručný popis události")
        self.popis_edit.setMinimumHeight(100)

        form.addRow("Datum:", self.datum_edit)
        form.addRow("Čas:", self.cas_edit)
        form.addRow("Typ události:", self.typ_edit)
        form.addRow("Popis:", self.popis_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if entry is not None:
            if entry.get("datum"):
                self.datum_edit.set_date_iso(entry.get("datum"))
            self.cas_edit.setText(entry.get("cas") or "")
            self.typ_edit.setText(entry.get("typ") or "")
            self.popis_edit.setPlainText(entry.get("popis") or "")
        elif default_date is not None:
            self.datum_edit.set_date_value(default_date)

    def get_entry(self) -> dict:
        date_value = self.datum_edit.get_date()
        return {
            "datum": date_value.isoformat() if date_value is not None else "",
            "cas": self.cas_edit.text().strip(),
            "typ": self.typ_edit.text().strip(),
            "popis": self.popis_edit.toPlainText().strip(),
        }
