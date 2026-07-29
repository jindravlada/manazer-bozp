from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.ares_service import ares_service
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    default_abbreviation,
)


class CoordinationEmployerDialog(QDialog):
    """Přidání / úprava zúčastněného zaměstnavatele (COORD-002)."""

    def __init__(self, parent=None, employer=None, *, main_only_abbreviation: bool = False):
        super().__init__(parent)
        self.employer = employer
        self.main_only_abbreviation = main_only_abbreviation or (
            employer is not None and bool(employer.is_main)
        )
        self.setWindowTitle(
            "Upravit zaměstnavatele" if employer is not None else "Přidat zaměstnavatele"
        )
        configure_resizable_form_dialog(self, width=520, height=420, min_width=420, min_height=320)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.ico = QLineEdit()
        self.company_name = QLineEdit()
        self.address = QLineEdit()
        self.abbreviation = QLineEdit()
        self.abbreviation.setMaxLength(32)
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        ico_row = QHBoxLayout()
        ico_row.addWidget(self.ico, 1)
        self.load_ares_button = QPushButton("Načíst z ARES")
        self.load_ares_button.clicked.connect(self.load_from_ares)
        ico_row.addWidget(self.load_ares_button)
        ico_host = QWidget()
        ico_host.setLayout(ico_row)

        form.addRow("IČO:", ico_host)
        form.addRow("Název *:", self.company_name)
        form.addRow("Adresa:", self.address)
        form.addRow("Zkratka:", self.abbreviation)
        form.addRow("Poznámka:", self.note)

        if employer is None:
            hint = QLabel(
                "Vyhledejte firmu podle IČO v ARES, nebo vyplňte údaje ručně. "
                "Po načtení z ARES lze hodnoty upravit."
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if employer is not None:
            self.ico.setText(employer.ico or "")
            self.company_name.setText(employer.company_name or "")
            self.address.setText(employer.address or "")
            self.abbreviation.setText(employer.abbreviation or "")
            self.note.setPlainText(employer.note or "")

        self._update_abbreviation_placeholder()

        if self.main_only_abbreviation:
            self.ico.setReadOnly(True)
            self.company_name.setReadOnly(True)
            self.address.setReadOnly(True)
            self.note.setReadOnly(True)
            self.load_ares_button.setEnabled(False)
            self.load_ares_button.setVisible(False)
            main_hint = QLabel(
                "Hlavního zaměstnavatele nelze odstranit. "
                "Upravit lze pouze zkratku."
            )
            main_hint.setWordWrap(True)
            layout.insertWidget(0, main_hint)

        self.company_name.textChanged.connect(self._update_abbreviation_placeholder)

    def _update_abbreviation_placeholder(self) -> None:
        suggested = default_abbreviation(self.company_name.text())
        self.abbreviation.setPlaceholderText(
            f"automaticky: {suggested}" if suggested else ""
        )

    def load_from_ares(self) -> None:
        ico = self.ico.text().strip()
        if not ico:
            QMessageBox.warning(self, "ARES", "Zadejte IČO.")
            return
        try:
            data = ares_service.find_by_ico(ico)
        except Exception as exc:  # noqa: BLE001 – síťová chyba ARES
            QMessageBox.critical(
                self,
                "ARES",
                f"Nepodařilo se načíst data z ARES.\n\n{exc}",
            )
            return
        if not data:
            QMessageBox.warning(self, "ARES", "Záznam nebyl nalezen.")
            return
        self.ico.setText(str(data.get("ico") or ico))
        self.company_name.setText(data.get("name") or "")
        self.address.setText(data.get("address") or "")
        self._update_abbreviation_placeholder()

    def get_data(self) -> dict:
        if self.main_only_abbreviation:
            return {"abbreviation": self.abbreviation.text().strip()}
        return {
            "company_name": self.company_name.text().strip(),
            "ico": self.ico.text().strip(),
            "address": self.address.text().strip(),
            "abbreviation": self.abbreviation.text().strip(),
            "note": self.note.toPlainText().strip(),
        }
