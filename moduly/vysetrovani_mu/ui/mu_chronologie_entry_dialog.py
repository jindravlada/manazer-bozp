from datetime import date

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.vysetrovani_mu.ui.mu_time_edit import MuTimeLineEdit


def _paired_fields(*pairs: tuple[str, QWidget]) -> QWidget:
    """Datum a čas milníku na jednom řádku."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for label, widget in pairs:
        layout.addWidget(QLabel(label))
        if widget.inherits("QLineEdit"):
            widget.setMinimumWidth(88)
            layout.addWidget(widget, 1)
        else:
            if hasattr(widget, "line_edit"):
                widget.line_edit.setMinimumWidth(96)
            layout.addWidget(widget, 2)
    return row


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
        self.cas_edit = MuTimeLineEdit()
        self.typ_edit = QLineEdit()
        self.typ_edit.setPlaceholderText("např. Oznámení, Ohledání místa")
        self.popis_edit = QTextEdit()
        self.popis_edit.setPlaceholderText("Stručný popis události")
        self.popis_edit.setMinimumHeight(100)

        form.addRow(_paired_fields(("Datum", self.datum_edit), ("Čas", self.cas_edit)))
        form.addRow("Typ události:", self.typ_edit)
        form.addRow("Popis:", self.popis_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if entry is not None:
            if entry.get("datum"):
                self.datum_edit.set_date_iso(entry.get("datum"))
            self.cas_edit.set_stored_text(entry.get("cas") or "")
            self.typ_edit.setText(entry.get("typ") or "")
            self.popis_edit.setPlainText(entry.get("popis") or "")
        elif default_date is not None:
            self.datum_edit.set_date_value(default_date)

    def accept(self) -> None:
        if self.cas_edit.blocks_save():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Čas zadejte ve tvaru HH:MM, nebo pole vymažte.",
            )
            self.cas_edit.setFocus()
            return
        super().accept()

    def get_entry(self) -> dict:
        date_value = self.datum_edit.get_date()
        return {
            "datum": date_value.isoformat() if date_value is not None else "",
            "cas": self.cas_edit.value_for_save(),
            "typ": self.typ_edit.text().strip(),
            "popis": self.popis_edit.toPlainText().strip(),
        }
