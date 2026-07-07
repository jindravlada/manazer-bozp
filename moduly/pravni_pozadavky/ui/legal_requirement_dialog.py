from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
from core.shared.widgets.entity_links_widget import EntityLinksWidget
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_LABELS,
    VALID_COMPLIANCE_STATUSES,
    VALID_PERIODICITIES,
    legal_document_display_label,
    legal_requirement_source_display_label,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_requirement_sanctions_tab import LegalRequirementSanctionsTab


class LegalRequirementDialog(QDialog):
    def __init__(self, parent=None, requirement=None, draft=None):
        super().__init__(parent)
        self.requirement = requirement
        self.draft = draft
        self._source_section_id: int | None = None
        self._processing_status: str | None = None

        self.setWindowTitle("Právní požadavek" if requirement is None else "Upravit požadavek")
        configure_resizable_form_dialog(self, width=760, height=680, min_width=560, min_height=480)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), "Požadavek")
        self.sanctions_tab = LegalRequirementSanctionsTab(
            requirement.id if requirement is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.sanctions_tab), "Sankce")
        self.links_widget = EntityLinksWidget(
            ENTITY_LEGAL_REQUIREMENT,
            requirement.id if requirement is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.links_widget), "Vazby")
        layout.addWidget(self.tabs, 1)
        add_save_cancel_footer(layout, self)

        if requirement is not None:
            self._load_requirement(requirement)
        elif draft is not None:
            self._load_draft(draft)
        else:
            self.active_checkbox.setChecked(True)
            self._populate_legal_sections()

    def _main_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.regulation_name = QLineEdit()
        self.regulation_number = QLineEdit()
        self.provision = QLineEdit()
        self.legal_document = QComboBox()
        self._populate_legal_documents()
        self.legal_section = QComboBox()
        self.source_section_display = QLineEdit()
        self.source_section_display.setReadOnly(True)
        self.area = QLineEdit()
        self.requirement_summary = QTextEdit()
        self.requirement_summary.setMinimumHeight(80)
        self.organization_impact = QTextEdit()
        self.organization_impact.setMinimumHeight(80)
        self.responsible_person = ThpWorkerSelector()
        self.periodicity = QComboBox()
        self.periodicity.addItem("", "")
        for key in sorted(PERIODICITY_LABELS, key=lambda item: PERIODICITY_LABELS[item]):
            self.periodicity.addItem(PERIODICITY_LABELS[key], key)
        self.last_verification = NullableDateEdit()
        self.next_verification = NullableDateEdit()
        self.compliance_status = QComboBox()
        for key in sorted(COMPLIANCE_STATUS_LABELS, key=lambda item: COMPLIANCE_STATUS_LABELS[item]):
            self.compliance_status.addItem(COMPLIANCE_STATUS_LABELS[key], key)
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)
        self.active_checkbox = QCheckBox("Aktivní záznam")

        form.addRow("Název předpisu:", self.regulation_name)
        form.addRow("Číslo předpisu:", self.regulation_number)
        form.addRow("Paragraf / ustanovení:", self.provision)
        form.addRow("Právní předpis:", self.legal_document)
        form.addRow("Ustanovení předpisu:", self.legal_section)
        form.addRow("Zdroj:", self.source_section_display)
        form.addRow("Stručný požadavek:", self.requirement_summary)
        form.addRow("Dopad na organizaci:", self.organization_impact)
        form.addRow("Odpovědná osoba:", self.responsible_person)
        form.addRow("Periodicita ověření:", self.periodicity)
        form.addRow("Poslední ověření:", self.last_verification)
        form.addRow("Další ověření:", self.next_verification)
        form.addRow("Stav plnění:", self.compliance_status)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        self.legal_document.currentIndexChanged.connect(self._on_legal_document_changed)
        return tab

    def _load_requirement(self, requirement) -> None:
        self._populate_legal_documents(selected_id=requirement.legal_document_id)
        self._populate_legal_sections(
            selected_id=requirement.legal_section_id,
            document_id=requirement.legal_document_id,
        )
        self.regulation_name.setText(requirement.regulation_name)
        self.regulation_number.setText(requirement.regulation_number)
        self.provision.setText(self._provision_display_text(requirement.provision, requirement.legal_section_id))
        self.area.setText(requirement.area)
        self.requirement_summary.setPlainText(requirement.requirement_summary)
        self.organization_impact.setPlainText(requirement.organization_impact)
        self.responsible_person.set_person_id(requirement.responsible_person_id)
        self._set_combo_value(self.periodicity, requirement.verification_periodicity)
        self.last_verification.set_date_value(requirement.last_verification_date)
        self.next_verification.set_date_value(requirement.next_verification_date)
        self._set_combo_value(self.compliance_status, requirement.compliance_status)
        self.note.setPlainText(requirement.note)
        self.active_checkbox.setChecked(requirement.active)
        self._source_section_id = requirement.source_section_id
        self._processing_status = requirement.processing_status
        self._update_source_section_display()

    def _load_draft(self, draft) -> None:
        self._populate_legal_documents(selected_id=draft.legal_document_id)
        self._populate_legal_sections(
            selected_id=draft.legal_section_id,
            document_id=draft.legal_document_id,
        )
        self.regulation_name.setText(draft.regulation_name)
        self.regulation_number.setText(draft.regulation_number)
        self.provision.setText(self._provision_display_text(draft.provision, draft.legal_section_id))
        self.area.setText(draft.area)
        self.requirement_summary.setPlainText(draft.requirement_summary)
        self.organization_impact.setPlainText(draft.organization_impact)
        self.active_checkbox.setChecked(draft.active)
        self._source_section_id = draft.source_section_id
        self._processing_status = draft.processing_status
        self._update_source_section_display()

    def _update_source_section_display(self) -> None:
        if self._source_section_id is None:
            self.source_section_display.clear()
            return
        section = legal_section_service.get_by_id(self._source_section_id)
        if section is None:
            self.source_section_display.clear()
            return
        document = legal_document_service.get_by_id(section.legal_document_id)
        sections_by_id = legal_section_service.build_sections_map([section])
        self.source_section_display.setText(
            legal_requirement_source_display_label(
                document,
                section,
                sections_by_id=sections_by_id,
            ),
        )

    def _provision_display_text(self, provision: str, section_id: int | None) -> str:
        if section_id is None:
            return provision
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return provision
        sections_by_id = legal_section_service.build_sections_map([section])
        return legal_section_provision_label(section, sections_by_id=sections_by_id)

    def _sync_regulation_name_from_document(self, document_id: int | None) -> None:
        if document_id is None:
            return
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            return
        self.regulation_name.setText(document.title.strip())

    def _populate_legal_documents(self, *, selected_id: int | None = None) -> None:
        self.legal_document.blockSignals(True)
        self.legal_document.clear()
        self.legal_document.addItem("— bez vazby —", None)

        documents = legal_document_service.list_all(include_inactive=False)
        selected_document = None
        if selected_id is not None:
            selected_document = legal_document_service.get_by_id(selected_id)
            if (
                selected_document is not None
                and not selected_document.active
                and all(item.id != selected_id for item in documents)
            ):
                documents = [selected_document, *documents]

        for document in documents:
            label = legal_document_display_label(document)
            if not label:
                label = f"Předpis #{document.id}"
            self.legal_document.addItem(label, document.id)

        if selected_id is not None:
            self._set_combo_value(self.legal_document, selected_id)
            self._sync_regulation_name_from_document(selected_id)
        self.legal_document.blockSignals(False)

    def _populate_legal_sections(
        self,
        *,
        selected_id: int | None = None,
        document_id: int | None = None,
    ) -> None:
        if document_id is None:
            document_id = self.legal_document.currentData()

        self.legal_section.clear()
        self.legal_section.addItem("— bez vazby —", None)

        sections = legal_section_service.list_for_selector(document_id=document_id)
        selected_section = None
        if selected_id is not None:
            selected_section = legal_section_service.get_by_id(selected_id)
            if (
                selected_section is not None
                and not selected_section.active
                and all(item.id != selected_id for item in sections)
            ):
                sections = [selected_section, *sections]

        sections_by_id = legal_section_service.build_sections_map(sections)
        for section in sections:
            label = legal_section_provision_label(section, sections_by_id=sections_by_id)
            if not label:
                label = f"Ustanovení #{section.id}"
            self.legal_section.addItem(label, section.id)

        if selected_id is not None:
            self._set_combo_value(self.legal_section, selected_id)

    def _on_legal_document_changed(self) -> None:
        selected_section_id = self.legal_section.currentData()
        document_id = self.legal_document.currentData()
        self._sync_regulation_name_from_document(document_id)
        if selected_section_id is not None:
            section = legal_section_service.get_by_id(selected_section_id)
            if section is not None and document_id is not None:
                if section.legal_document_id != document_id:
                    selected_section_id = None
            elif section is not None and document_id is None:
                pass
        self._populate_legal_sections(
            selected_id=selected_section_id,
            document_id=document_id,
        )

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def get_data(self) -> dict:
        periodicity = self.periodicity.currentData() or ""
        compliance_status = self.compliance_status.currentData() or ""
        if periodicity not in VALID_PERIODICITIES:
            periodicity = ""
        if compliance_status not in VALID_COMPLIANCE_STATUSES:
            compliance_status = ""

        return {
            "regulation_name": self.regulation_name.text().strip(),
            "regulation_number": self.regulation_number.text().strip(),
            "provision": self.provision.text().strip(),
            "legal_document_id": self.legal_document.currentData(),
            "legal_section_id": self.legal_section.currentData(),
            "source_section_id": self._source_section_id,
            "area": self.area.text().strip(),
            "requirement_summary": self.requirement_summary.toPlainText().strip(),
            "organization_impact": self.organization_impact.toPlainText().strip(),
            "responsible_person_id": self.responsible_person.current_person_id(),
            "verification_periodicity": periodicity,
            "last_verification_date": self.last_verification.get_date(),
            "next_verification_date": self.next_verification.get_date(),
            "compliance_status": compliance_status,
            "processing_status": self._processing_status or "",
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
