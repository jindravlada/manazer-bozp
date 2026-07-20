from PySide6.QtWidgets import (
    QComboBox,
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
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_abbreviation,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    CoordinationParticipantError,
    coordination_participant_service,
    snapshot_from_employee,
)


class CoordinationParticipantDialog(QDialog):
    """Přidání / úprava účastníka schůzky (COORD-003 / UX-COORD-12a)."""

    def __init__(
        self,
        parent=None,
        participant=None,
        *,
        coordination_id: int | None = None,
        default_employer_id: int | None = None,
    ):
        super().__init__(parent)
        self.participant = participant
        if coordination_id is not None:
            self.coordination_id = coordination_id
        elif participant is not None:
            employer = coordination_employer_service.get_by_id(
                participant.coordination_employer_id
            )
            self.coordination_id = employer.coordination_id if employer else None
        else:
            self.coordination_id = None
        self.setWindowTitle(
            "Upravit účastníka" if participant is not None else "Přidat účastníka"
        )
        configure_resizable_form_dialog(
            self, width=520, height=480, min_width=420, min_height=360
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.employer = QComboBox()
        self.source_group = QButtonGroup(self)
        self.source_employee = QRadioButton("Vybrat z evidence THP / zaměstnanců")
        self.source_manual = QRadioButton("Zadat ručně")
        self.source_group.addButton(self.source_employee)
        self.source_group.addButton(self.source_manual)
        self.source_manual.setChecked(True)

        self.employee_selector = ThpWorkerSelector(
            include_empty=True, allow_custom_value=False
        )
        self.employee_selector.currentIndexChanged.connect(self._on_employee_selected)

        self.full_name = QLineEdit()
        self.role = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        self.source_host = QWidget()
        source_layout = QVBoxLayout(self.source_host)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_employee)
        source_layout.addWidget(self.source_manual)

        form.addRow("Zaměstnavatel *:", self.employer)
        form.addRow("Způsob zadání:", self.source_host)
        form.addRow("THP pracovník:", self.employee_selector)
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

        self.source_employee.toggled.connect(self._update_source_mode)
        self.source_manual.toggled.connect(self._update_source_mode)
        self.employer.currentIndexChanged.connect(self._on_employer_changed)

        preserve_employer = (
            participant.coordination_employer_id
            if participant is not None
            else default_employer_id
        )
        if preserve_employer is None and self.coordination_id is not None:
            preserve_employer = coordination_participant_service.default_employer_id(
                self.coordination_id
            )
        self._reload_employers(preserve_id=preserve_employer)

        if participant is not None:
            self.employer.setEnabled(False)
            self.source_host.hide()
            self.employee_selector.hide()
            self.full_name.setText(participant.full_name or "")
            self.role.setText(participant.role or "")
            self.phone.setText(participant.phone or "")
            self.email.setText(participant.email or "")
            self.note.setPlainText(participant.note or "")
        else:
            hint = QLabel(
                "Údaje z evidence se uloží jako snapshot do koordinace. "
                "Pozdější změna pracovníka v evidenci je neovlivní."
            )
            hint.setWordWrap(True)
            self._thp_hint = hint
            layout.insertWidget(0, hint)
            self._sync_employee_source_visibility()
            self._update_source_mode()

    def _reload_employers(self, *, preserve_id: int | None = None) -> None:
        self.employer.blockSignals(True)
        self.employer.clear()
        if self.coordination_id is None:
            self.employer.blockSignals(False)
            return
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        for item in employers:
            if not item.active and item.id != preserve_id:
                continue
            label = employer_abbreviation(item) or (item.company_name or "").strip()
            if not label:
                label = item.company_name or f"#{item.id}"
            if not item.active:
                label = f"{label} (neaktivní)"
            self.employer.addItem(label, item.id)
        if preserve_id is not None:
            index = self.employer.findData(preserve_id)
            if index >= 0:
                self.employer.setCurrentIndex(index)
        self.employer.blockSignals(False)

    def _current_employer(self):
        employer_id = self.employer.currentData()
        if not isinstance(employer_id, int):
            return None
        return coordination_employer_service.get_by_id(employer_id)

    def _sync_employee_source_visibility(self) -> None:
        if self.participant is not None:
            return
        employer = self._current_employer()
        allow = bool(employer is not None and employer.is_main and employer.active)
        self.source_host.setVisible(allow)
        self.employee_selector.setVisible(allow)
        hint = getattr(self, "_thp_hint", None)
        if hint is not None:
            hint.setVisible(allow)
        if not allow:
            self.source_manual.setChecked(True)

    def _on_employer_changed(self) -> None:
        if self.participant is not None:
            return
        self._sync_employee_source_visibility()
        self._update_source_mode()

    def _update_source_mode(self) -> None:
        if self.participant is not None:
            return
        employer = self._current_employer()
        allow = bool(employer is not None and employer.is_main and employer.active)
        use_employee = allow and self.source_employee.isChecked()
        self.employee_selector.setEnabled(use_employee)
        if use_employee:
            self._on_employee_selected()
        else:
            self.employee_selector.set_person_id(None)

    def _on_employee_selected(self) -> None:
        employer = self._current_employer()
        allow = bool(employer is not None and employer.is_main and employer.active)
        if not (allow and self.source_employee.isChecked()):
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

        employer_id = self.employer.currentData()
        data["coordination_employer_id"] = (
            int(employer_id) if isinstance(employer_id, int) else None
        )
        employer = self._current_employer()
        allow = bool(employer is not None and employer.is_main and employer.active)
        if allow and self.source_employee.isChecked():
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
