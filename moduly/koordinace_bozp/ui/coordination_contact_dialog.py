from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.constants import (
    CONTACT_TYPES,
    CONTACT_TYPES_SELECTABLE,
    CONTACT_TYPE_LABELS,
    DEFAULT_CONTACT_TYPE,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    coordination_contact_service,
)


class CoordinationContactDialog(QDialog):
    """Přidání / úprava kontaktu koordinace (COORD-010)."""

    def __init__(
        self,
        parent=None,
        *,
        coordination_id: int,
        contact=None,
    ):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self.contact = contact
        self._loading = False
        self.setWindowTitle(
            "Upravit kontakt" if contact is not None else "Přidat kontakt"
        )
        configure_resizable_form_dialog(
            self,
            width=560,
            height=480,
            min_width=440,
            min_height=360,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.source_group = QButtonGroup(self)
        self.source_participant = QRadioButton("Vybrat z účastníků schůzky")
        self.source_manual = QRadioButton("Zadat ručně")
        self.source_group.addButton(self.source_participant)
        self.source_group.addButton(self.source_manual)
        self.source_manual.setChecked(True)

        self.participant = QComboBox()
        self.contact_type = QComboBox()
        current_type = (
            (contact.contact_type or "").strip() if contact is not None else ""
        )
        for type_id in CONTACT_TYPES:
            if type_id in CONTACT_TYPES_SELECTABLE or type_id == current_type:
                self.contact_type.addItem(CONTACT_TYPE_LABELS[type_id], type_id)
        self.custom_name = QLineEdit()
        self.role = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)

        source_host = QWidget()
        source_layout = QVBoxLayout(source_host)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_participant)
        source_layout.addWidget(self.source_manual)
        form.addRow("Způsob zadání:", source_host)
        form.addRow("Účastník:", self.participant)
        form.addRow("Typ kontaktu *:", self.contact_type)
        form.addRow("Jméno *:", self.custom_name)
        form.addRow("Funkce / role:", self.role)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("Poznámka:", self.note)
        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.source_participant.toggled.connect(self._update_source_mode)
        self.source_manual.toggled.connect(self._update_source_mode)
        self.participant.currentIndexChanged.connect(self._on_participant_changed)

        preserve_participant = contact.participant_id if contact is not None else None
        self._reload_participants(preserve_id=preserve_participant)

        if contact is not None:
            if contact.participant_id:
                self.source_participant.setChecked(True)
            else:
                self.source_manual.setChecked(True)
            index = self.contact_type.findData(contact.contact_type)
            self.contact_type.setCurrentIndex(index if index >= 0 else 0)
            self.custom_name.setText(contact.custom_name or "")
            self.role.setText(contact.role or "")
            self.phone.setText(contact.phone or "")
            self.email.setText(contact.email or "")
            self.note.setPlainText(contact.note or "")
        else:
            self.contact_type.setCurrentIndex(
                self.contact_type.findData(DEFAULT_CONTACT_TYPE)
            )

        self._update_source_mode()

    def _reload_participants(self, *, preserve_id: int | None = None) -> None:
        self._loading = True
        try:
            self.participant.clear()
            self.participant.addItem("— vyberte účastníka —", None)
            found_preserve = False
            for item in coordination_contact_service.list_selectable_participants(
                self.coordination_id
            ):
                label = item.full_name or f"Účastník #{item.id}"
                if item.role:
                    label = f"{label} ({item.role})"
                self.participant.addItem(label, item.id)
                if preserve_id is not None and item.id == preserve_id:
                    found_preserve = True
            if preserve_id is not None and not found_preserve and self.contact is not None:
                label = self.contact.custom_name or f"Účastník #{preserve_id}"
                self.participant.addItem(f"{label} (neaktivní)", preserve_id)
            if preserve_id is not None:
                index = self.participant.findData(preserve_id)
                if index >= 0:
                    self.participant.setCurrentIndex(index)
        finally:
            self._loading = False

    def _update_source_mode(self) -> None:
        from_participant = self.source_participant.isChecked()
        self.participant.setEnabled(from_participant)
        if (
            from_participant
            and self.participant.currentData() is not None
            and self.contact is None
        ):
            self._apply_participant_snapshot(self.participant.currentData())

    def _on_participant_changed(self) -> None:
        if self._loading or not self.source_participant.isChecked():
            return
        participant_id = self.participant.currentData()
        if isinstance(participant_id, int):
            # Nepřepisuj snapshot při editaci již uloženého kontaktu se stejným účastníkem.
            if (
                self.contact is not None
                and self.contact.participant_id == participant_id
            ):
                return
            self._apply_participant_snapshot(participant_id)

    def _apply_participant_snapshot(self, participant_id: int) -> None:
        try:
            snapshot = coordination_contact_service.snapshot_from_participant(
                participant_id
            )
        except Exception:  # noqa: BLE001
            return
        self.custom_name.setText(snapshot["custom_name"])
        self.role.setText(snapshot["role"])
        self.phone.setText(snapshot["phone"])
        self.email.setText(snapshot["email"])

    def get_data(self) -> dict:
        from_participant = self.source_participant.isChecked()
        participant_id = None
        if from_participant:
            participant_id = self.participant.currentData()
            if (
                not isinstance(participant_id, int)
                and self.contact is not None
                and self.contact.participant_id
            ):
                participant_id = self.contact.participant_id
        return {
            "contact_type": self.contact_type.currentData() or DEFAULT_CONTACT_TYPE,
            "participant_id": (
                int(participant_id) if isinstance(participant_id, int) else None
            ),
            "custom_name": self.custom_name.text(),
            "role": self.role.text(),
            "phone": self.phone.text(),
            "email": self.email.text(),
            "note": self.note.toPlainText(),
        }
