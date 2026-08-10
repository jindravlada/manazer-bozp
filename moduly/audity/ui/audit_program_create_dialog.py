"""Dialog pro vytvoření nebo úpravu programu auditů."""

from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.audity.constants import (
    AUDIT_PROGRAM_CREATE_DIALOG_TITLE,
    AUDIT_PROGRAM_EDIT_DIALOG_TITLE,
    AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL,
    AUDIT_PROGRAM_STANDARDS_V1,
    AUDIT_STANDARD_ISO_45001,
    AUDIT_STANDARD_ISO_9001,
)
from moduly.audity.modely.audit_program import AuditProgram
from moduly.audity.sluzby.audit_program_service import audit_program_service


class AuditProgramCreateDialog(QDialog):
    """Formulář nového nebo upravovaného programu auditů."""

    def __init__(self, parent=None, *, program: AuditProgram | None = None):
        super().__init__(parent)

        self._program = program
        self.setWindowTitle(
            AUDIT_PROGRAM_EDIT_DIALOG_TITLE if program is not None else AUDIT_PROGRAM_CREATE_DIALOG_TITLE
        )
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit()
        self._date_from_edit = NullableDateEdit()
        self._date_to_edit = NullableDateEdit()
        self._iso_45001_check = QCheckBox(AUDIT_STANDARD_ISO_45001)
        self._iso_9001_check = QCheckBox(AUDIT_STANDARD_ISO_9001)
        self._description_edit = QTextEdit()
        self._description_edit.setMinimumHeight(90)
        self._note_edit = QTextEdit()
        self._note_edit.setMinimumHeight(70)
        self._previous_program_combo = QComboBox()

        self._iso_45001_check.setChecked(True)
        self._iso_9001_check.setChecked(True)

        form.addRow("Název:", self._name_edit)
        form.addRow("Datum od:", self._date_from_edit)
        form.addRow("Datum do:", self._date_to_edit)
        form.addRow(AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL, self._previous_program_combo)
        form.addRow("Normy:", self._iso_45001_check)
        form.addRow("", self._iso_9001_check)
        form.addRow("Popis:", self._description_edit)
        form.addRow("Poznámka:", self._note_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if program is not None:
            self._load_program(program)
        self._populate_previous_programs(program.id if program is not None else None)

    def _populate_previous_programs(self, current_program_id: int | None) -> None:
        self._previous_program_combo.blockSignals(True)
        self._previous_program_combo.clear()
        self._previous_program_combo.addItem("— žádný —", None)
        selected_id = None
        if self._program is not None:
            selected_id = self._program.previous_program_id
        for program in audit_program_service.list_programs():
            if current_program_id is not None and program.id == current_program_id:
                continue
            self._previous_program_combo.addItem(program.name, program.id)
        if selected_id is not None:
            index = self._previous_program_combo.findData(selected_id)
            if index >= 0:
                self._previous_program_combo.setCurrentIndex(index)
        self._previous_program_combo.blockSignals(False)

    def _load_program(self, program: AuditProgram) -> None:
        self._name_edit.setText(program.name)
        if program.date_from is not None:
            self._date_from_edit.set_date_value(program.date_from)
        if program.date_to is not None:
            self._date_to_edit.set_date_value(program.date_to)

        standards = set(audit_program_service.parse_standards(program.standards_json))
        self._iso_45001_check.setChecked(AUDIT_STANDARD_ISO_45001 in standards)
        self._iso_9001_check.setChecked(AUDIT_STANDARD_ISO_9001 in standards)
        self._description_edit.setPlainText(program.description)
        self._note_edit.setPlainText(program.note)

    def _accept_if_valid(self) -> None:
        if not self.program_payload()["name"]:
            self._name_edit.setFocus()
            return
        if self.program_payload()["date_from"] is None or self.program_payload()["date_to"] is None:
            return
        if not self._selected_standards():
            return
        self.accept()

    def _selected_standards(self) -> list[str]:
        standards: list[str] = []
        if self._iso_45001_check.isChecked():
            standards.append(AUDIT_STANDARD_ISO_45001)
        if self._iso_9001_check.isChecked():
            standards.append(AUDIT_STANDARD_ISO_9001)
        return standards

    def program_payload(self) -> dict:
        return {
            "name": self._name_edit.text().strip(),
            "date_from": self._date_from_edit.get_date(),
            "date_to": self._date_to_edit.get_date(),
            "standards": self._selected_standards() or list(AUDIT_PROGRAM_STANDARDS_V1),
            "description": self._description_edit.toPlainText().strip(),
            "note": self._note_edit.toPlainText().strip(),
            "previous_program_id": self._previous_program_combo.currentData(),
        }

    @staticmethod
    def default_period() -> tuple[date, date]:
        today = date.today()
        start_year = today.year if today.month < 4 else today.year + 1
        return date(start_year, 4, 1), date(start_year + 3, 3, 31)

    def set_default_period(self) -> None:
        date_from, date_to = self.default_period()
        self._date_from_edit.set_date_value(date_from)
        self._date_to_edit.set_date_value(date_to)
