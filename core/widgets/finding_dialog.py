from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_TYPE_ZJISTENI,
    VALID_FINDING_STATUSES,
    VALID_FINDING_TYPES,
)
from core.shared.finding_display import FINDING_STATUS_LABELS, FINDING_TYPE_LABELS
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector


class FindingDialog(QDialog):
    def __init__(self, parent=None, finding=None, *, title: str = "Zjištění"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(680, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        for finding_type in sorted(VALID_FINDING_TYPES):
            self.type_combo.addItem(FINDING_TYPE_LABELS[finding_type], finding_type)

        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText(
            "např. Bod 4, Kap. 5.2, ISO 9001 čl. 8.4, Checklist 12, Směrnice S-01"
        )

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Popis zjištění")
        self.description_edit.setMinimumHeight(90)

        self.recommended_action_edit = QTextEdit()
        self.recommended_action_edit.setPlaceholderText("Doporučené opatření")
        self.recommended_action_edit.setMinimumHeight(80)

        self.person_selector = ThpWorkerSelector()
        self.due_date_edit = NullableDateEdit()

        self.status_combo = QComboBox()
        for status in sorted(VALID_FINDING_STATUSES):
            self.status_combo.addItem(FINDING_STATUS_LABELS[status], status)

        self.resolution_note_edit = QTextEdit()
        self.resolution_note_edit.setPlaceholderText("Poznámka k vypořádání")
        self.resolution_note_edit.setMinimumHeight(80)

        form.addRow("Typ:", self.type_combo)
        form.addRow("Reference:", self.reference_edit)
        form.addRow("Popis:", self.description_edit)
        form.addRow("Doporučené opatření:", self.recommended_action_edit)
        form.addRow("Odpovědná osoba:", self.person_selector)
        form.addRow("Termín:", self.due_date_edit)
        form.addRow("Stav:", self.status_combo)
        form.addRow("Poznámka k vypořádání:", self.resolution_note_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if finding is not None:
            type_index = self.type_combo.findData(finding.finding_type)
            if type_index >= 0:
                self.type_combo.setCurrentIndex(type_index)
            self.reference_edit.setText(finding.reference_label or "")
            self.description_edit.setPlainText(finding.description or "")
            self.recommended_action_edit.setPlainText(finding.recommended_action or "")
            if finding.responsible_person_id:
                self.person_selector.set_person_id(finding.responsible_person_id)
            elif finding.responsible_person_name:
                self.person_selector.setCurrentText(finding.responsible_person_name)
            self.due_date_edit.set_date_value(finding.due_date)
            status_index = self.status_combo.findData(finding.status)
            if status_index >= 0:
                self.status_combo.setCurrentIndex(status_index)
            self.resolution_note_edit.setPlainText(finding.resolution_note or "")
        else:
            default_index = self.type_combo.findData(FINDING_TYPE_ZJISTENI)
            if default_index >= 0:
                self.type_combo.setCurrentIndex(default_index)
            default_status = self.status_combo.findData(FINDING_STATUS_OTEVRENE)
            if default_status >= 0:
                self.status_combo.setCurrentIndex(default_status)

    def get_data(self) -> dict:
        person = self.person_selector.current_person()
        person_id = self.person_selector.current_person_id()
        person_name = person.display_name if person else self.person_selector.currentText().strip()

        return {
            "finding_type": self.type_combo.currentData(),
            "reference_label": self.reference_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "recommended_action": self.recommended_action_edit.toPlainText().strip(),
            "responsible_person_id": person_id,
            "responsible_person_name": person_name,
            "due_date": self.due_date_edit.get_date(),
            "status": self.status_combo.currentData(),
            "resolution_note": self.resolution_note_edit.toPlainText().strip(),
        }
