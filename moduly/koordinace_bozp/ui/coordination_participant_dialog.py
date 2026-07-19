from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
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
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.koordinace_bozp.constants import (
    COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
    COORDINATION_PARTICIPANT_SOURCE_MANUAL,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    CoordinationParticipantError,
    snapshot_from_employee,
)


class CoordinationParticipantDialog(QDialog):
    """Přidání / úprava účastníka schůzky (COORD-003)."""

    def __init__(
        self,
        parent=None,
        participant=None,
        *,
        allow_employee_source: bool = False,
    ):
        super().__init__(parent)
        self.participant = participant
        self.allow_employee_source = allow_employee_source and participant is None
        self.setWindowTitle(
            "Upravit účastníka" if participant is not None else "Přidat účastníka"
        )
        configure_resizable_form_dialog(self, width=520, height=440, min_width=420, min_height=340)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.source_group = QButtonGroup(self)
        self.source_employee = QRadioButton("Vybrat z evidence THP / zaměstnanců")
        self.source_manual = QRadioButton("Zadat ručně")
        self.source_group.addButton(self.source_employee)
        self.source_group.addButton(self.source_manual)
        self.source_manual.setChecked(True)

        self.employee_selector = ThpWorkerSelector(include_empty=True, allow_custom_value=False)
        self.employee_selector.currentIndexChanged.connect(self._on_employee_selected)

        self.full_name = QLineEdit()
        self.role = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        if self.allow_employee_source:
            source_host = QWidget()
            source_layout = QVBoxLayout(source_host)
            source_layout.setContentsMargins(0, 0, 0, 0)
            source_layout.addWidget(self.source_employee)
            source_layout.addWidget(self.source_manual)
            form.addRow("Způsob zadání:", source_host)
            form.addRow("THP pracovník:", self.employee_selector)
            self.source_employee.toggled.connect(self._update_source_mode)
            self.source_manual.toggled.connect(self._update_source_mode)
        else:
            self.source_employee.hide()
            self.source_manual.hide()
            self.employee_selector.hide()

        form.addRow("Jméno a příjmení *:", self.full_name)
        form.addRow("Funkce / role:", self.role)
        form.addRow("Telefon:", self.phone)
        form.addRow("E-mail:", self.email)
        form.addRow("Poznámka:", self.note)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if participant is not None:
            self.full_name.setText(participant.full_name or "")
            self.role.setText(participant.role or "")
            self.phone.setText(participant.phone or "")
            self.email.setText(participant.email or "")
            self.note.setPlainText(participant.note or "")
        elif self.allow_employee_source:
            hint = QLabel(
                "Údaje z evidence se uloží jako snapshot do koordinace. "
                "Pozdější změna pracovníka v evidenci je neovlivní."
            )
            hint.setWordWrap(True)
            layout.insertWidget(0, hint)
            self._update_source_mode()

    def _update_source_mode(self) -> None:
        use_employee = self.allow_employee_source and self.source_employee.isChecked()
        self.employee_selector.setEnabled(use_employee)
        if use_employee:
            self._on_employee_selected()
        else:
            self.employee_selector.set_person_id(None)

    def _on_employee_selected(self) -> None:
        if not (self.allow_employee_source and self.source_employee.isChecked()):
            return
        worker = self.employee_selector.current_person()
        if worker is None:
            return
        try:
            snapshot = snapshot_from_employee(worker.id)
        except CoordinationParticipantError:
            return
        self.full_name.setText(snapshot["full_name"])
        self.role.setText(snapshot["role"])
        self.phone.setText(snapshot["phone"])
        self.email.setText(snapshot["email"])

    def get_data(self) -> dict:
        data = {
            "full_name": self.full_name.text().strip(),
            "role": self.role.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "note": self.note.toPlainText().strip(),
        }
        if self.participant is not None:
            return data

        if self.allow_employee_source and self.source_employee.isChecked():
            employee_id = self.employee_selector.current_person_id()
            return {
                "person_source_type": COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
                "employee_id": employee_id,
                **data,
            }
        return {
            "person_source_type": COORDINATION_PARTICIPANT_SOURCE_MANUAL,
            "employee_id": None,
            **data,
        }
