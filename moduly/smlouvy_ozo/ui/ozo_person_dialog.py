"""Karta údajů odborně způsobilé osoby."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.smlouvy_ozo.constants import DIALOG_TITLE_OZO_PERSON
from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service


class OzoPersonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE_OZO_PERSON)
        configure_resizable_form_dialog(
            self, width=560, height=420, min_width=420, min_height=320
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.residence_address = QLineEdit()
        self.exam_date = NullableDateEdit()
        self.certificate_number = QLineEdit()
        self.certificate_valid_to = NullableDateEdit()
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(60)

        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Adresa bydliště / trvalého pobytu:", self.residence_address)
        form.addRow("Datum zkoušky / periodické zkoušky:", self.exam_date)
        form.addRow("Číslo osvědčení:", self.certificate_number)
        form.addRow("Platnost osvědčení do:", self.certificate_valid_to)
        form.addRow("Poznámka:", self.note)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = create_save_cancel_box(self, is_new=False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load()

    def _load(self) -> None:
        person = ozo_person_service.get_or_empty()
        self.first_name.setText(person.first_name or "")
        self.last_name.setText(person.last_name or "")
        self.residence_address.setText(person.residence_address or "")
        self.exam_date.set_date_value(person.exam_date)
        self.certificate_number.setText(person.certificate_number or "")
        self.certificate_valid_to.set_date_value(person.certificate_valid_to)
        self.note.setPlainText(person.note or "")

    def get_data(self) -> dict:
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "residence_address": self.residence_address.text().strip(),
            "exam_date": self.exam_date.get_date(),
            "certificate_number": self.certificate_number.text().strip(),
            "certificate_valid_to": self.certificate_valid_to.get_date(),
            "note": self.note.toPlainText().strip(),
        }

    def _save(self) -> None:
        try:
            ozo_person_service.save(**self.get_data())
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, DIALOG_TITLE_OZO_PERSON, str(error))
            return
        self.accept()
