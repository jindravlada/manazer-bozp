"""Karta údajů odborně způsobilé osoby."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.smlouvy_ozo.constants import (
    DIALOG_TITLE_OZO_PERSON,
    ENTITY_OZO_PERSON,
)
from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service


class OzoPersonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.person = ozo_person_service.get()
        self.setWindowTitle(DIALOG_TITLE_OZO_PERSON)
        configure_resizable_form_dialog(
            self, width=600, height=560, min_width=440, min_height=400
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)

        fields = QWidget()
        form = QFormLayout(fields)
        self.title_before = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.title_after = QLineEdit()
        self.residence_address = QLineEdit()
        self.exam_date = NullableDateEdit()
        self.certificate_number = QLineEdit()
        self.certificate_valid_to = NullableDateEdit()
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(60)

        form.addRow("Titul před jménem:", self.title_before)
        form.addRow("Jméno:", self.first_name)
        form.addRow("Příjmení:", self.last_name)
        form.addRow("Titul za jménem:", self.title_after)
        form.addRow("Adresa bydliště / trvalého pobytu:", self.residence_address)
        form.addRow("Datum zkoušky / periodické zkoušky:", self.exam_date)
        form.addRow("Číslo osvědčení:", self.certificate_number)
        form.addRow("Platnost osvědčení do:", self.certificate_valid_to)
        form.addRow("Poznámka:", self.note)
        form_layout.addWidget(fields)

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments_hint = QLabel(
            "Přílohy (např. sken osvědčení OZO) lze přidat až po uložení záznamu."
        )
        self.attachments_hint.setObjectName("MutedText")
        self.attachments_hint.setWordWrap(True)
        self.attachments = AttachmentWidget(
            ENTITY_OZO_PERSON,
            self.person.id if self.person is not None else None,
        )
        attachments_layout.addWidget(self.attachments_hint)
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=self.person is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=self.person is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        if self.person is not None:
            self._load(self.person)
        self._sync_attachments_hint()
        self._editor.capture_baseline()

    def _load(self, person) -> None:
        self.title_before.setText(getattr(person, "title_before", "") or "")
        self.first_name.setText(person.first_name or "")
        self.last_name.setText(person.last_name or "")
        self.title_after.setText(getattr(person, "title_after", "") or "")
        self.residence_address.setText(person.residence_address or "")
        self.exam_date.set_date_value(person.exam_date)
        self.certificate_number.setText(person.certificate_number or "")
        self.certificate_valid_to.set_date_value(person.certificate_valid_to)
        self.note.setPlainText(person.note or "")

    def _sync_attachments_hint(self) -> None:
        has_id = self.person is not None and self.person.id is not None
        self.attachments_hint.setVisible(not has_id)

    def get_data(self) -> dict:
        return {
            "title_before": self.title_before.text().strip(),
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "title_after": self.title_after.text().strip(),
            "residence_address": self.residence_address.text().strip(),
            "exam_date": self.exam_date.get_date(),
            "certificate_number": self.certificate_number.text().strip(),
            "certificate_valid_to": self.certificate_valid_to.get_date(),
            "note": self.note.toPlainText().strip(),
        }

    def _save(self) -> bool:
        try:
            self.person = ozo_person_service.save(**self.get_data())
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(self, DIALOG_TITLE_OZO_PERSON, str(error))
            return False
        self.attachments.set_entity(ENTITY_OZO_PERSON, self.person.id)
        self._sync_attachments_hint()
        return True
