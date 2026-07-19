from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.koordinace_bozp.constants import TAB_COORDINATOR
from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
    CoordinationCoordinatorError,
    coordination_coordinator_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    coordination_participant_service,
)


class CoordinationCoordinatorTab(QWidget):
    """Záložka pověřeného koordinátora BOZP (COORD-005 / UX-COORD-2)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._loading = False
        self._last_participant_id: int | None = None

        layout = QVBoxLayout(self)

        self.unavailable_label = QLabel(
            "Koordinátora BOZP lze nastavit po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #c62828;")
        self.warning_label.hide()
        content_layout.addWidget(self.warning_label)

        form = QFormLayout()

        self.source_group = QButtonGroup(self)
        self.source_participant = QRadioButton("Vybrat z účastníků")
        self.source_manual = QRadioButton("Zadat ručně")
        self.source_group.addButton(self.source_participant)
        self.source_group.addButton(self.source_manual)
        self.source_participant.setChecked(True)

        source_host = QWidget()
        source_layout = QVBoxLayout(source_host)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_participant)
        source_layout.addWidget(self.source_manual)
        form.addRow("Způsob zadání:", source_host)

        self.employer_combo = QComboBox()
        self.participant_combo = QComboBox()
        self.full_name = QLineEdit()
        self.employer_name = QLineEdit()
        self.role = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(80)

        form.addRow("Pověřený zaměstnavatel:", self.employer_combo)
        form.addRow("Pověřená osoba:", self.participant_combo)
        form.addRow("Jméno *:", self.full_name)
        form.addRow("Organizace:", self.employer_name)
        form.addRow("Funkce:", self.role)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("Poznámka:", self.note)
        content_layout.addLayout(form)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Uložit koordinátora")
        buttons.addWidget(self.save_btn)
        buttons.addStretch()
        content_layout.addLayout(buttons)
        content_layout.addStretch()
        layout.addWidget(self.content)

        self.source_participant.toggled.connect(self._update_source_mode)
        self.source_manual.toggled.connect(self._update_source_mode)
        self.employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        self.participant_combo.currentIndexChanged.connect(self._on_participant_changed)
        self.save_btn.clicked.connect(self.save_coordinator)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh()
        else:
            self._clear_form()

    def refresh(self) -> None:
        if self.coordination_id is None:
            return
        self._loading = True
        try:
            coordination_employer_service.ensure_main_employer(self.coordination_id)
            saved = coordination_coordinator_service.get_for_coordination(
                self.coordination_id,
                include_inactive=True,
            )
            if saved is not None and saved.participant_id:
                self.source_participant.setChecked(True)
            elif saved is not None:
                self.source_manual.setChecked(True)
            else:
                self.source_participant.setChecked(True)

            self._reload_employers(
                preferred_employer_id=(
                    saved.employer_id if saved is not None else None
                )
            )
            preferred_participant_id = (
                saved.participant_id if saved is not None else None
            )
            self._reload_participants(preferred_participant_id=preferred_participant_id)
            self._last_participant_id = preferred_participant_id

            if saved is not None:
                self.full_name.setText(saved.full_name or "")
                self.employer_name.setText(saved.employer_name or "")
                self.role.setText(saved.role or "")
                self.phone.setText(saved.phone or "")
                self.email.setText(saved.email or "")
                self.note.setPlainText(saved.note or "")
            else:
                self.full_name.clear()
                self.employer_name.clear()
                self.role.clear()
                self.phone.clear()
                self.email.clear()
                self.note.clear()
            self._update_source_mode()
            self._update_warning(saved)
        finally:
            self._loading = False

    def save_coordinator(self) -> None:
        if self.coordination_id is None:
            return
        try:
            if self.source_participant.isChecked():
                employer_id = self.employer_combo.currentData()
                participant_id = self.participant_combo.currentData()
                if not isinstance(employer_id, int):
                    QMessageBox.warning(
                        self,
                        TAB_COORDINATOR,
                        "Vyberte pověřeného zaměstnavatele.",
                    )
                    return
                if not isinstance(participant_id, int):
                    QMessageBox.warning(
                        self,
                        TAB_COORDINATOR,
                        "Vyberte pověřenou osobu z účastníků schůzky.",
                    )
                    return
                coordination_coordinator_service.set_coordinator(
                    self.coordination_id,
                    employer_id=employer_id,
                    participant_id=participant_id,
                    note=self.note.toPlainText().strip(),
                )
            else:
                coordination_coordinator_service.set_coordinator(
                    self.coordination_id,
                    full_name=self.full_name.text(),
                    employer_name=self.employer_name.text(),
                    role=self.role.text(),
                    phone=self.phone.text(),
                    email=self.email.text(),
                    note=self.note.toPlainText().strip(),
                )
        except CoordinationCoordinatorError as error:
            QMessageBox.warning(self, TAB_COORDINATOR, str(error))
            return
        QMessageBox.information(self, TAB_COORDINATOR, "Koordinátor byl uložen.")
        self.refresh()

    def _update_source_mode(self) -> None:
        from_participant = self.source_participant.isChecked()
        self.employer_combo.setEnabled(from_participant)
        self.participant_combo.setEnabled(from_participant)
        for widget in (
            self.full_name,
            self.employer_name,
            self.role,
            self.phone,
            self.email,
        ):
            widget.setReadOnly(from_participant)
        if from_participant:
            self._apply_participant_snapshot(overwrite=False)

    def _on_employer_changed(self) -> None:
        if self._loading:
            return
        self._reload_participants()
        self._last_participant_id = None
        if self.source_participant.isChecked():
            self._clear_identity_fields()
        self._update_warning(None)

    def _on_participant_changed(self) -> None:
        if self._loading or not self.source_participant.isChecked():
            return
        self._apply_participant_snapshot(overwrite=True)

    def _apply_participant_snapshot(self, *, overwrite: bool) -> None:
        participant_id = self.participant_combo.currentData()
        if not isinstance(participant_id, int):
            if overwrite:
                self._clear_identity_fields()
            self._last_participant_id = None
            return
        if not overwrite and self._last_participant_id == participant_id:
            return
        try:
            snapshot = coordination_coordinator_service.snapshot_from_participant(
                participant_id
            )
        except CoordinationCoordinatorError:
            return
        self.full_name.setText(snapshot["full_name"])
        self.employer_name.setText(snapshot["employer_name"])
        self.role.setText(snapshot["role"])
        self.phone.setText(snapshot["phone"])
        self.email.setText(snapshot["email"])
        self._last_participant_id = participant_id

    def _clear_identity_fields(self) -> None:
        self.full_name.clear()
        self.employer_name.clear()
        self.role.clear()
        self.phone.clear()
        self.email.clear()

    def _reload_employers(self, *, preferred_employer_id: int | None = None) -> None:
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.employer_combo.blockSignals(True)
        self.employer_combo.clear()
        self.employer_combo.addItem("", None)
        for employer in employers:
            if not employer.active and employer.id != preferred_employer_id:
                continue
            label = f"{employer.abbreviation} – {employer.company_name}".strip(" –")
            if not employer.active:
                label = f"{label} (neaktivní)"
            self.employer_combo.addItem(label, employer.id)
        if preferred_employer_id is not None:
            index = self.employer_combo.findData(preferred_employer_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.employer_combo.blockSignals(False)

    def _reload_participants(
        self,
        *,
        preferred_participant_id: int | None = None,
    ) -> None:
        employer_id = self.employer_combo.currentData()
        self.participant_combo.blockSignals(True)
        self.participant_combo.clear()
        self.participant_combo.addItem("", None)
        if isinstance(employer_id, int):
            participants = coordination_participant_service.list_for_employer(
                employer_id,
                include_inactive=True,
            )
            for participant in participants:
                if not participant.active and participant.id != preferred_participant_id:
                    continue
                label = participant.full_name or ""
                if participant.role:
                    label = f"{label} ({participant.role})"
                if not participant.active:
                    label = f"{label} (neaktivní)"
                if participant.active or participant.id == preferred_participant_id:
                    self.participant_combo.addItem(label, participant.id)
            if preferred_participant_id is not None:
                index = self.participant_combo.findData(preferred_participant_id)
                if index >= 0:
                    self.participant_combo.setCurrentIndex(index)
        self.participant_combo.blockSignals(False)

    def _update_warning(self, saved) -> None:
        messages: list[str] = []
        coordinator = saved
        if coordinator is None and self.coordination_id is not None:
            coordinator = coordination_coordinator_service.get_for_coordination(
                self.coordination_id,
                include_inactive=True,
            )
        if coordinator is None:
            self.warning_label.hide()
            self.warning_label.clear()
            return

        if coordinator.employer_id:
            employer = coordination_employer_service.get_by_id(coordinator.employer_id)
            if employer is not None and not employer.active:
                messages.append(
                    "Pověřený zaměstnavatel je deaktivovaný. "
                    "Vazba na koordinátora zůstává."
                )
        if coordinator.participant_id:
            participant = coordination_participant_service.get_by_id(
                coordinator.participant_id
            )
            if participant is not None and not participant.active:
                messages.append(
                    "Pověřená osoba je deaktivovaná. "
                    "Koordinátora automaticky nerušíme."
                )
        if messages:
            self.warning_label.setText(" ".join(messages))
            self.warning_label.show()
        else:
            self.warning_label.hide()
            self.warning_label.clear()

    def _clear_form(self) -> None:
        self.employer_combo.clear()
        self.participant_combo.clear()
        self._clear_identity_fields()
        self.note.clear()
        self.warning_label.hide()
        self.source_participant.setChecked(True)
