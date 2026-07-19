from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from moduly.koordinace_bozp.constants import (
    COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
    TAB_PARTICIPANTS,
)
from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
    coordination_coordinator_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    CoordinationParticipantError,
    coordination_participant_service,
)
from moduly.koordinace_bozp.ui.coordination_participant_dialog import (
    CoordinationParticipantDialog,
)
from moduly.koordinace_bozp.ui.coordination_participant_table import (
    CoordinationParticipantTable,
)


class CoordinationParticipantsTab(QWidget):
    """Záložka účastníků koordinační schůzky (COORD-003)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id

        layout = QVBoxLayout(self)

        self.unavailable_label = QLabel(
            "Účastníky schůzky lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        employer_row = QHBoxLayout()
        employer_row.addWidget(QLabel("Zaměstnavatel:"))
        self.employer_combo = QComboBox()
        self.employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        employer_row.addWidget(self.employer_combo, 1)
        content_layout.addLayout(employer_row)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        content_layout.addLayout(toolbar)

        self.table = CoordinationParticipantTable()
        configure_table_columns(self.table, "coordination_participants")
        content_layout.addWidget(self.table)
        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_participant)
        self.edit_btn.clicked.connect(self.edit_selected_participant)
        self.activate_btn.clicked.connect(self.activate_selected_participant)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_participant)
        self.table.doubleClicked.connect(self.edit_selected_participant)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh_employers()
        else:
            self.employer_combo.clear()
            self.table.setRowCount(0)
            self._update_action_buttons()

    def refresh_employers(self) -> None:
        if self.coordination_id is None:
            return
        coordination_employer_service.ensure_main_employer(self.coordination_id)
        previous_id = self.current_employer_id()
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.employer_combo.blockSignals(True)
        self.employer_combo.clear()
        for employer in employers:
            label = f"{employer.abbreviation} – {employer.company_name}".strip(" –")
            if not employer.active:
                label = f"{label} (neaktivní)"
            self.employer_combo.addItem(label, employer.id)
        self.employer_combo.blockSignals(False)

        if previous_id is not None:
            index = self.employer_combo.findData(previous_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.refresh_participants()

    def refresh_participants(self) -> None:
        employer_id = self.current_employer_id()
        if employer_id is None:
            self.table.setRowCount(0)
            self._update_action_buttons()
            return
        participants = coordination_participant_service.list_for_employer(
            employer_id,
            include_inactive=True,
        )
        self.table.load_participants(participants)
        configure_table_columns(self.table, "coordination_participants")
        self.table.clear_selection()
        self._update_action_buttons()

    def current_employer_id(self) -> int | None:
        data = self.employer_combo.currentData()
        return int(data) if isinstance(data, int) else None

    def current_employer(self):
        employer_id = self.current_employer_id()
        if employer_id is None:
            return None
        return coordination_employer_service.get_by_id(employer_id)

    def add_participant(self) -> None:
        employer = self.current_employer()
        if employer is None:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Vyberte zaměstnavatele.")
            return
        if not employer.active:
            QMessageBox.warning(
                self,
                TAB_PARTICIPANTS,
                "K deaktivovanému zaměstnavateli nelze přidat účastníka.",
            )
            return
        dialog = CoordinationParticipantDialog(
            self,
            allow_employee_source=bool(employer.is_main),
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            if data.get("person_source_type") == COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE:
                employee_id = data.get("employee_id")
                if not employee_id:
                    raise CoordinationParticipantError(
                        "Vyberte pracovníka z evidence THP."
                    )
                coordination_participant_service.add_from_employee(
                    employer.id,
                    employee_id,
                    full_name=data["full_name"],
                    role=data["role"],
                    phone=data["phone"],
                    email=data["email"],
                    note=data["note"],
                )
            else:
                coordination_participant_service.add_manual(
                    employer.id,
                    full_name=data["full_name"],
                    role=data["role"],
                    phone=data["phone"],
                    email=data["email"],
                    note=data["note"],
                )
        except CoordinationParticipantError as error:
            QMessageBox.warning(self, TAB_PARTICIPANTS, str(error))
            return
        self.refresh_participants()

    def edit_selected_participant(self) -> None:
        participant = self._selected_participant()
        if participant is None:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Vyberte účastníka.")
            return
        dialog = CoordinationParticipantDialog(self, participant=participant)
        if not dialog.exec():
            return
        try:
            coordination_participant_service.update_participant(
                participant.id,
                **dialog.get_data(),
            )
        except CoordinationParticipantError as error:
            QMessageBox.warning(self, TAB_PARTICIPANTS, str(error))
            return
        self.refresh_participants()

    def activate_selected_participant(self) -> None:
        participant = self._selected_participant()
        if participant is None:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Vyberte účastníka.")
            return
        if participant.active:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Účastník je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat účastníka {participant.full_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            coordination_participant_service.activate(participant.id)
            self.refresh_participants()

    def deactivate_selected_participant(self) -> None:
        participant = self._selected_participant()
        if participant is None:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Vyberte účastníka.")
            return
        if not participant.active:
            QMessageBox.information(self, TAB_PARTICIPANTS, "Účastník je již neaktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat účastníka {participant.full_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        is_coordinator = coordination_coordinator_service.is_participant_coordinator(
            participant.id
        )
        coordination_participant_service.deactivate(participant.id)
        if is_coordinator:
            QMessageBox.warning(
                self,
                TAB_PARTICIPANTS,
                "Účastník je pověřeným koordinátorem BOZP. "
                "Vazba na koordinátora zůstává – koordinátora automaticky nerušíme.",
            )
        self.refresh_participants()

    def _on_employer_changed(self) -> None:
        self.refresh_participants()

    def _selected_participant(self):
        participant_id = self.table.selected_participant_id()
        if participant_id is None:
            return None
        return coordination_participant_service.get_by_id(participant_id)

    def _update_action_buttons(self) -> None:
        employer = self.current_employer()
        can_add = employer is not None and bool(employer.active)
        self.add_btn.setEnabled(can_add)

        participant = self._selected_participant()
        has_selection = participant is not None
        self.edit_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not participant.active)
        self.deactivate_btn.setEnabled(participant.active)
