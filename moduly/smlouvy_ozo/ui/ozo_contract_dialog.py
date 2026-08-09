"""Editor smlouvy OZO."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.ares_service import ares_service
from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.smlouvy_ozo.constants import (
    DEFAULT_NOTIFY_BEFORE_UNIT,
    DEFAULT_NOTIFY_BEFORE_VALUE,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    ENTITY_OZO_CONTRACT,
    EMPLOYER_NAME_REQUIRED_MESSAGE,
    NOTIFY_UNITS,
    UNIT_LABELS,
    VALID_FROM_REQUIRED_MESSAGE,
    VALID_TO_REQUIRED_MESSAGE,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
    OzoContractValidationError,
    ozo_contract_service,
)


class OzoContractDialog(QDialog):
    def __init__(self, parent=None, contract=None):
        super().__init__(parent)
        self.contract = contract
        self.setWindowTitle(
            DIALOG_TITLE_EDIT if contract is not None else DIALOG_TITLE_NEW
        )
        configure_resizable_form_dialog(
            self, width=720, height=720, min_width=560, min_height=520
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)

        form_layout.addWidget(self._employer_group())
        form_layout.addWidget(self._contact_group())
        form_layout.addWidget(self._contract_group())

        attachments_box = QGroupBox("Přílohy")
        attachments_layout = QVBoxLayout(attachments_box)
        self.attachments_hint = QLabel(
            "Přílohy (smlouva, dodatky, související dokumenty) "
            "lze přidat až po uložení záznamu."
        )
        self.attachments_hint.setObjectName("MutedText")
        self.attachments_hint.setWordWrap(True)
        self.attachments = AttachmentWidget(
            ENTITY_OZO_CONTRACT,
            contract.id if contract is not None else None,
        )
        attachments_layout.addWidget(self.attachments_hint)
        attachments_layout.addWidget(self.attachments)
        form_layout.addWidget(attachments_box)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=contract is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=contract is None,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        self.indefinite_checkbox.toggled.connect(self._sync_validity_fields)
        if contract is not None:
            self._load(contract)
        self._sync_validity_fields()
        self._sync_attachments_hint()
        self._editor.capture_baseline()

    def _employer_group(self) -> QGroupBox:
        box = QGroupBox("Objednatel")
        form = QFormLayout(box)
        self.employer_name = QLineEdit()
        self.ico = QLineEdit()
        self.address = QLineEdit()

        ico_row = QHBoxLayout()
        ico_row.addWidget(self.ico, 1)
        self.load_ares_button = QPushButton("Načíst z ARES")
        self.load_ares_button.clicked.connect(self.load_from_ares)
        ico_row.addWidget(self.load_ares_button)
        ico_host = QWidget()
        ico_host.setLayout(ico_row)

        form.addRow("Název *:", self.employer_name)
        form.addRow("IČO:", ico_host)
        form.addRow("Sídlo:", self.address)
        return box

    def _contact_group(self) -> QGroupBox:
        box = QGroupBox("Kontakt")
        form = QFormLayout(box)
        self.contact_person = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        form.addRow("Kontaktní osoba:", self.contact_person)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        return box

    def _contract_group(self) -> QGroupBox:
        box = QGroupBox("Smlouva")
        form = QFormLayout(box)
        self.contract_number = QLineEdit()
        self.signed_on = NullableDateEdit()
        self.valid_from = NullableDateEdit()
        self.indefinite_checkbox = QCheckBox("Na dobu neurčitou")
        self.valid_to = NullableDateEdit()

        self.notify_before_value = QSpinBox()
        self.notify_before_value.setRange(0, 9999)
        self.notify_before_value.setValue(DEFAULT_NOTIFY_BEFORE_VALUE)
        self.notify_before_unit = QComboBox()
        for unit in NOTIFY_UNITS:
            self.notify_before_unit.addItem(UNIT_LABELS[unit], unit)
        self.notify_before_unit.setCurrentIndex(
            NOTIFY_UNITS.index(DEFAULT_NOTIFY_BEFORE_UNIT)
        )
        notify_row = QHBoxLayout()
        notify_row.addWidget(self.notify_before_value)
        notify_row.addWidget(self.notify_before_unit, 1)
        notify_row.addWidget(QLabel("předem"))
        self.notify_widget = QWidget()
        self.notify_widget.setLayout(notify_row)

        self.services_scope = QTextEdit()
        self.services_scope.setAcceptRichText(False)
        self.services_scope.setMinimumHeight(70)
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(70)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Číslo smlouvy:", self.contract_number)
        form.addRow("Datum uzavření:", self.signed_on)
        form.addRow("Platnost od *:", self.valid_from)
        form.addRow("", self.indefinite_checkbox)
        form.addRow("Platnost do:", self.valid_to)
        form.addRow("Upozornit před koncem:", self.notify_widget)
        form.addRow("Rozsah poskytovaných služeb:", self.services_scope)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)
        return box

    def _load(self, contract) -> None:
        self.employer_name.setText(contract.employer_name or "")
        self.ico.setText(contract.ico or "")
        self.address.setText(contract.address or "")
        self.contact_person.setText(contract.contact_person or "")
        self.phone.setText(contract.phone or "")
        self.email.setText(contract.email or "")
        self.contract_number.setText(contract.contract_number or "")
        self.signed_on.set_date_value(contract.signed_on)
        self.valid_from.set_date_value(contract.valid_from)
        self.indefinite_checkbox.setChecked(bool(contract.indefinite))
        self.valid_to.set_date_value(contract.valid_to)
        self.notify_before_value.setValue(
            int(contract.notify_before_value)
            if contract.notify_before_value is not None
            else DEFAULT_NOTIFY_BEFORE_VALUE
        )
        unit_index = self.notify_before_unit.findData(
            contract.notify_before_unit or DEFAULT_NOTIFY_BEFORE_UNIT
        )
        if unit_index >= 0:
            self.notify_before_unit.setCurrentIndex(unit_index)
        self.services_scope.setPlainText(contract.services_scope or "")
        self.note.setPlainText(contract.note or "")
        self.active_checkbox.setChecked(bool(contract.active))

    def _sync_validity_fields(self) -> None:
        indefinite = self.indefinite_checkbox.isChecked()
        self.valid_to.setEnabled(not indefinite)
        self.notify_widget.setEnabled(not indefinite)
        if indefinite:
            self.valid_to.clear_date()

    def _sync_attachments_hint(self) -> None:
        has_id = self.contract is not None and self.contract.id is not None
        self.attachments_hint.setVisible(not has_id)

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
        self.employer_name.setText(data.get("name") or "")
        self.address.setText(data.get("address") or "")

    def get_data(self) -> dict:
        return {
            "employer_name": self.employer_name.text().strip(),
            "ico": self.ico.text().strip(),
            "address": self.address.text().strip(),
            "contact_person": self.contact_person.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "contract_number": self.contract_number.text().strip(),
            "signed_on": self.signed_on.get_date(),
            "valid_from": self.valid_from.get_date(),
            "valid_to": self.valid_to.get_date(),
            "indefinite": self.indefinite_checkbox.isChecked(),
            "notify_before_value": int(self.notify_before_value.value()),
            "notify_before_unit": self.notify_before_unit.currentData()
            or DEFAULT_NOTIFY_BEFORE_UNIT,
            "services_scope": self.services_scope.toPlainText().strip(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }

    def _save(self) -> bool:
        data = self.get_data()
        if not data["employer_name"]:
            QMessageBox.warning(self, self.windowTitle(), EMPLOYER_NAME_REQUIRED_MESSAGE)
            return False
        if data["valid_from"] is None:
            QMessageBox.warning(self, self.windowTitle(), VALID_FROM_REQUIRED_MESSAGE)
            return False
        if not data["indefinite"] and data["valid_to"] is None:
            QMessageBox.warning(self, self.windowTitle(), VALID_TO_REQUIRED_MESSAGE)
            return False
        try:
            if self.contract is None:
                self.contract = ozo_contract_service.create(**data)
            else:
                self.contract = ozo_contract_service.update(self.contract.id, **data)
        except OzoContractValidationError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        self.attachments.set_entity(ENTITY_OZO_CONTRACT, self.contract.id)
        self._sync_attachments_hint()
        self.setWindowTitle(DIALOG_TITLE_EDIT)
        return True
