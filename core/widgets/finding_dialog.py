from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box, configure_resizable_form_dialog, wrap_in_scroll_area

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
    def __init__(
        self,
        parent=None,
        finding=None,
        *,
        title: str = "Zjištění",
        allowed_finding_types=None,
        default_finding_type=None,
        knowledge_source: dict | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        configure_resizable_form_dialog(self, width=680, height=560, min_width=520, min_height=400)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        if knowledge_source:
            form.addRow("Zdroj:", self._readonly_label(str(knowledge_source.get("source_label") or "—")))
            form.addRow("Oblast:", self._readonly_label(str(knowledge_source.get("area_label") or "—")))
            form.addRow("Sekce:", self._readonly_label(str(knowledge_source.get("section_label") or "—")))
            form.addRow(
                "Kontrolní bod:",
                self._readonly_label(str(knowledge_source.get("control_point_label") or "—")),
            )

        self.type_combo = QComboBox()
        finding_types = sorted(allowed_finding_types or VALID_FINDING_TYPES)
        for finding_type in finding_types:
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

        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
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
            default_type = default_finding_type or (
                finding_types[0] if allowed_finding_types else FINDING_TYPE_ZJISTENI
            )
            default_index = self.type_combo.findData(default_type)
            if default_index >= 0:
                self.type_combo.setCurrentIndex(default_index)
            default_status = self.status_combo.findData(FINDING_STATUS_OTEVRENE)
            if default_status >= 0:
                self.status_combo.setCurrentIndex(default_status)

            if knowledge_source:
                control_point = str(knowledge_source.get("control_point_label") or "").strip()
                if control_point:
                    self.reference_edit.setText(control_point)

    @staticmethod
    def _readonly_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label

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
