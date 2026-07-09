from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import add_save_cancel_footer, configure_resizable_form_dialog
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_STATUS_LABELS,
    VALID_COMPLIANCE_STATUSES,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
    calculate_next_verification_date,
    legal_requirement_service,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_task_service import (
    legal_requirement_task_service,
)


class LegalRequirementCheckDialog(QDialog):
    def __init__(self, parent=None, requirement=None):
        super().__init__(parent)
        self.requirement = requirement
        self.created_task = None
        self._syncing_next_check = False
        self._next_check_manual_override = False

        self.setWindowTitle("Ověřit plnění")
        configure_resizable_form_dialog(self, width=620, height=420, min_width=480, min_height=320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.check_date = DateEdit()
        self.result = QComboBox()
        for key in sorted(COMPLIANCE_STATUS_LABELS, key=lambda item: COMPLIANCE_STATUS_LABELS[item]):
            self.result.addItem(COMPLIANCE_STATUS_LABELS[key], key)
        self.comment = QTextEdit()
        self.comment.setMinimumHeight(90)
        self.next_check_date = NullableDateEdit()
        self.create_task_checkbox = QCheckBox("Založit úkol při nesplnění / částečném splnění")

        form.addRow("Datum ověření:", self.check_date)
        form.addRow("Výsledek:", self.result)
        form.addRow("Komentář:", self.comment)
        form.addRow("Další termín ověření:", self.next_check_date)
        form.addRow("", self.create_task_checkbox)

        layout.addLayout(form)
        add_save_cancel_footer(layout, self)

        self.result.currentIndexChanged.connect(self._update_task_checkbox)
        self.check_date.dateChanged.connect(self._on_check_date_changed)
        self.next_check_date.dateChanged.connect(self._on_next_check_manually_changed)
        self._suggest_next_check_date(force=True)
        self._update_task_checkbox()

    def _selected_result(self) -> str:
        value = self.result.currentData() or ""
        if value in VALID_COMPLIANCE_STATUSES:
            return value
        return ""

    def _update_task_checkbox(self) -> None:
        result = self._selected_result()
        enabled = result in (COMPLIANCE_NESPLNENO, COMPLIANCE_CASTECNE_SPLNENO)
        self.create_task_checkbox.setEnabled(enabled)
        if not enabled:
            self.create_task_checkbox.setChecked(False)

    def _on_check_date_changed(self) -> None:
        self._suggest_next_check_date(force=True)

    def _on_next_check_manually_changed(self) -> None:
        if self._syncing_next_check:
            return
        self._next_check_manual_override = True

    def _suggest_next_check_date(self, *, force: bool = False) -> None:
        if self.requirement is None:
            return
        if not force and self._next_check_manual_override:
            return

        check_date = self._check_date_value()
        periodicity = self.requirement.verification_periodicity
        if not periodicity:
            return

        suggested = calculate_next_verification_date(check_date, periodicity)
        if suggested is None:
            return

        self._syncing_next_check = True
        try:
            self.next_check_date.set_date_value(suggested)
            if force:
                self._next_check_manual_override = False
        finally:
            self._syncing_next_check = False

    def _check_date_value(self) -> date:
        iso = self.check_date.get_date_iso()
        year, month, day = [int(part) for part in iso.split("-")]
        return date(year, month, day)

    def accept(self) -> None:
        if self.requirement is None:
            QMessageBox.warning(self, "Ověření plnění", "Požadavek nebyl nalezen.")
            return

        result = self._selected_result()
        if not result:
            QMessageBox.warning(self, "Ověření plnění", "Vyberte výsledek ověření.")
            return

        updated = legal_requirement_service.record_verification(
            self.requirement.id,
            check_date=self._check_date_value(),
            result=result,
            comment=self.comment.toPlainText().strip(),
            next_check_date=self.next_check_date.get_date(),
        )
        if updated is None:
            QMessageBox.warning(self, "Ověření plnění", "Požadavek nebyl nalezen.")
            return

        if self.create_task_checkbox.isChecked():
            self.created_task = legal_requirement_task_service.create_task_from_requirement(
                self.requirement.id,
            )

        super().accept()
