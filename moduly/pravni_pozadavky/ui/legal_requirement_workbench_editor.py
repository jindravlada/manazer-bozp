from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.responsibility_role_selector import ResponsibilityRoleSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.pravni_pozadavky.constants import (
    PERIODICITY_LABELS,
    VALID_PERIODICITIES,
)


class LegalRequirementWorkbenchEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._requirement_id: int | None = None
        self._source_section_id: int | None = None
        self._legal_document_id: int | None = None
        self._legal_section_id: int | None = None
        self._regulation_number = ""
        self._provision = ""
        self._document_regulation_name = ""
        self._processing_status: str | None = None
        self._organization_impact = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.context_label = QLabel("Vyberte ustanovení ve stromu předpisu.")
        self.context_label.setWordWrap(True)
        self.context_label.setObjectName("InfoText")
        layout.addWidget(self.context_label)

        self.section_text = QTextEdit()
        self.section_text.setReadOnly(True)
        self.section_text.setMinimumHeight(80)
        self.section_text.setPlaceholderText("Text ustanovení")
        layout.addWidget(self.section_text)

        form = QFormLayout()
        self.regulation_name = QLineEdit()
        self.requirement_summary = QTextEdit()
        self.requirement_summary.setMinimumHeight(120)
        self.area = QLineEdit()
        self.responsible_person = ThpWorkerSelector()
        self.responsible_role = ResponsibilityRoleSelector()
        self.periodicity = QComboBox()
        self.periodicity.addItem("", "")
        for key in sorted(PERIODICITY_LABELS, key=lambda item: PERIODICITY_LABELS[item]):
            self.periodicity.addItem(PERIODICITY_LABELS[key], key)
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Název:", self.regulation_name)
        form.addRow("Způsob plnění:", self.requirement_summary)
        form.addRow("Oblast:", self.area)

        responsibility_group = QGroupBox("Odpovědnost")
        responsibility_form = QFormLayout(responsibility_group)
        responsibility_form.addRow("Osoba:", self.responsible_person)
        responsibility_form.addRow("Funkce / role:", self.responsible_role)
        form.addRow(responsibility_group)

        form.addRow("Periodicita:", self.periodicity)
        form.addRow("Poznámka:", self.note)
        layout.addLayout(form, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.save_btn = QPushButton("Uložit")
        self.next_btn = QPushButton("Další ustanovení")
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.next_btn)
        layout.addLayout(buttons)

        self._set_enabled(False)

    def clear_form(self) -> None:
        self._requirement_id = None
        self._source_section_id = None
        self._legal_document_id = None
        self._legal_section_id = None
        self._regulation_number = ""
        self._provision = ""
        self._document_regulation_name = ""
        self._processing_status = None
        self._organization_impact = ""
        self.context_label.setText("Vyberte ustanovení ve stromu předpisu.")
        self.section_text.clear()
        self.regulation_name.clear()
        self.requirement_summary.clear()
        self.area.clear()
        self.responsible_person.set_person_id(None)
        self.responsible_role.set_role_id(None)
        self.periodicity.setCurrentIndex(0)
        self.note.clear()
        self._set_enabled(False)

    def load_attachment_preview(self, *, section_text: str = "", context_label: str = "") -> None:
        self._requirement_id = None
        self._source_section_id = None
        self._legal_document_id = None
        self._legal_section_id = None
        self._regulation_number = ""
        self._provision = ""
        self._document_regulation_name = ""
        self._processing_status = None
        self._organization_impact = ""

        self.context_label.setText(context_label or "Příloha")
        self.section_text.setPlainText(section_text)
        self.regulation_name.clear()
        self.requirement_summary.clear()
        self.area.clear()
        self.responsible_person.set_person_id(None)
        self.responsible_role.set_role_id(None)
        self.periodicity.setCurrentIndex(0)
        self.note.clear()
        self._set_enabled(False)

    def load_requirement(
        self,
        requirement,
        *,
        section_id: int | None = None,
        section_text: str = "",
        context_label: str = "",
    ) -> None:
        self._requirement_id = requirement.id
        self._source_section_id = section_id if section_id is not None else requirement.source_section_id
        self._legal_document_id = requirement.legal_document_id
        self._legal_section_id = requirement.legal_section_id
        self._regulation_number = requirement.regulation_number
        self._provision = requirement.provision
        self._processing_status = requirement.processing_status
        self._organization_impact = requirement.organization_impact
        self._document_regulation_name = requirement.regulation_name

        self.context_label.setText(context_label or requirement.provision)
        self.section_text.setPlainText(section_text)
        self.regulation_name.setText(
            (requirement.title or requirement.regulation_name or "").strip(),
        )
        self.requirement_summary.setPlainText(requirement.requirement_summary)
        self.area.setText(requirement.area)
        self.responsible_person.set_person_id(requirement.responsible_person_id)
        self.responsible_role.set_role_id(
            requirement.responsible_role_id,
            requirement.responsible_role_name,
        )
        self._set_combo_value(self.periodicity, requirement.verification_periodicity)
        self.note.setPlainText(requirement.note)
        self._set_enabled(True)

    def load_draft(self, draft, *, section_text: str = "", context_label: str = "") -> None:
        self._requirement_id = None
        self._source_section_id = draft.source_section_id
        self._legal_document_id = draft.legal_document_id
        self._legal_section_id = draft.legal_section_id
        self._regulation_number = draft.regulation_number
        self._provision = draft.provision
        self._processing_status = draft.processing_status
        self._organization_impact = draft.organization_impact
        self._document_regulation_name = draft.regulation_name

        self.context_label.setText(context_label or draft.provision)
        self.section_text.setPlainText(section_text)
        self.regulation_name.clear()
        self.requirement_summary.setPlainText(section_text)
        self.area.setText(draft.area)
        self.responsible_person.set_person_id(None)
        self.responsible_role.set_role_id(None)
        self.periodicity.setCurrentIndex(0)
        self.note.clear()
        self._set_enabled(True)

    def current_section_id(self) -> int | None:
        return self._source_section_id

    def get_data(self) -> dict:
        periodicity = self.periodicity.currentData() or ""
        if periodicity not in VALID_PERIODICITIES:
            periodicity = ""

        data = {
            "title": self.regulation_name.text().strip(),
            "regulation_name": self._document_regulation_name,
            "regulation_number": self._regulation_number,
            "provision": self._provision,
            "legal_document_id": self._legal_document_id,
            "legal_section_id": self._legal_section_id,
            "area": self.area.text().strip(),
            "requirement_summary": self.requirement_summary.toPlainText().strip(),
            "organization_impact": self._organization_impact or "",
            "responsible_person_id": self.responsible_person.current_person_id(),
            "responsible_role_id": self.responsible_role.current_role_id(),
            "verification_periodicity": periodicity,
            "last_verification_date": None,
            "next_verification_date": None,
            "compliance_status": "",
            "processing_status": self._processing_status or "",
            "note": self.note.toPlainText().strip(),
            "active": True,
        }
        if self._requirement_id is None and self._source_section_id is not None:
            data["source_section_id"] = self._source_section_id
            data["source_section_ids"] = [self._source_section_id]
        return data

    def _set_enabled(self, enabled: bool) -> None:
        for widget in (
            self.section_text,
            self.regulation_name,
            self.requirement_summary,
            self.area,
            self.responsible_person,
            self.responsible_role,
            self.periodicity,
            self.note,
            self.save_btn,
            self.next_btn,
        ):
            widget.setEnabled(enabled)

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
