"""Dialog pro vytvoření nebo úpravu návštěvy v programu auditů."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.audity.constants import (
    AUDIT_PROGRAM_EDIT_VISIT_DIALOG_TITLE,
    AUDIT_PROGRAM_NEW_VISIT_DIALOG_TITLE,
    MONTH_NAMES_CAPITALIZED,
)
from moduly.audity.modely.audit_program import AuditProgramVisit


class AuditProgramVisitDialog(QDialog):
    def __init__(self, parent=None, *, visit: AuditProgramVisit | None = None):
        super().__init__(parent)

        self._visit = visit
        self.setWindowTitle(
            AUDIT_PROGRAM_EDIT_VISIT_DIALOG_TITLE
            if visit is not None
            else AUDIT_PROGRAM_NEW_VISIT_DIALOG_TITLE
        )
        self.resize(420, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._month_combo = QComboBox()
        for index, label in enumerate(MONTH_NAMES_CAPITALIZED, start=1):
            self._month_combo.addItem(label, index)

        self._year_spin = QSpinBox()
        self._year_spin.setRange(2000, 2100)
        self._year_spin.setValue(2026)

        self._planned_date_edit = NullableDateEdit()
        self._note_edit = QTextEdit()
        self._note_edit.setMinimumHeight(80)

        form.addRow("Měsíc:", self._month_combo)
        form.addRow("Rok:", self._year_spin)
        form.addRow("Plánované datum:", self._planned_date_edit)
        form.addRow("Poznámka:", self._note_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if visit is not None:
            self._load_visit(visit)

    def _load_visit(self, visit: AuditProgramVisit) -> None:
        if visit.planned_month is not None:
            index = self._month_combo.findData(visit.planned_month)
            if index >= 0:
                self._month_combo.setCurrentIndex(index)
        if visit.planned_year is not None:
            self._year_spin.setValue(visit.planned_year)
        if visit.planned_date is not None:
            self._planned_date_edit.set_date_value(visit.planned_date)
        self._note_edit.setPlainText(visit.note or "")

    def visit_payload(self) -> dict:
        return {
            "planned_month": int(self._month_combo.currentData()),
            "planned_year": self._year_spin.value(),
            "planned_date": self._planned_date_edit.get_date(),
            "note": self._note_edit.toPlainText().strip(),
        }
