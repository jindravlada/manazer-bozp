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
    legal_requirement_source_display_label,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_document_selector import LegalDocumentNameSelector
from moduly.pravni_pozadavky.ui.legal_requirement_sanctions_tab import LegalRequirementSanctionsTab


class LegalRequirementDialog(QDialog):
    def __init__(self, parent=None, requirement=None, draft=None):
        super().__init__(parent)
        self.requirement = requirement
        self.draft = draft
        self._source_section_id: int | None = None
        self._processing_status: str | None = None
        self._syncing_document_fields = False
        self._last_document_id: int | None = None

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

        self.regulation_name = LegalDocumentNameSelector()
        self.regulation_number = QLineEdit()
        self.provision = QLineEdit()
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
        form.addRow("Ustanovení:", self.provision)
        form.addRow("Ustanovení předpisu:", self.legal_section)
        form.addRow("Vychází z:", self.source_section_display)
        form.addRow("Způsob plnění:", self.requirement_summary)
        form.addRow("Dopad na organizaci:", self.organization_impact)
        form.addRow("Odpovědná osoba:", self.responsible_person)
        form.addRow("Periodicita ověření:", self.periodicity)
        form.addRow("Poslední ověření:", self.last_verification)
        form.addRow("Další ověření:", self.next_verification)
        form.addRow("Stav plnění:", self.compliance_status)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        self.regulation_name.document_changed.connect(self._on_regulation_name_changed)
        self.regulation_number.textChanged.connect(self._on_regulation_number_changed)
        self.legal_section.currentIndexChanged.connect(self._on_legal_section_changed)
        return tab

    def _load_requirement(self, requirement) -> None:
        self.regulation_name.reload(selected_id=requirement.legal_document_id)
        if requirement.legal_document_id is None:
            self.regulation_name.setCurrentText(requirement.regulation_name)
        self._last_document_id = requirement.legal_document_id
        self.regulation_number.setText(requirement.regulation_number)
        self._populate_legal_sections(
            selected_id=requirement.legal_section_id,
            document_id=requirement.legal_document_id,
        )
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
        self.regulation_name.reload(selected_id=draft.legal_document_id)
        self._last_document_id = draft.legal_document_id
        self.regulation_number.setText(draft.regulation_number)
        self._populate_legal_sections(
            selected_id=draft.legal_section_id,
            document_id=draft.legal_document_id,
        )
        self.provision.setText(self._provision_display_text(draft.provision, draft.legal_section_id))
        self.area.setText(draft.area)
        self.requirement_summary.setPlainText(draft.requirement_summary)
        self.organization_impact.setPlainText(draft.organization_impact)
        self.active_checkbox.setChecked(draft.active)
        self._source_section_id = draft.source_section_id
        self._processing_status = draft.processing_status
        self._update_source_section_display()

    def _current_legal_document_id(self) -> int | None:
        return self.regulation_name.current_document_id()

    def _on_regulation_name_changed(self) -> None:
        if self._syncing_document_fields:
            return

        new_document_id = self.regulation_name.current_document_id()

        self._syncing_document_fields = True
        try:
            if new_document_id is not None:
                document = self.regulation_name.current_document()
                if document is not None:
                    self.regulation_name.set_document_id_without_signal(document.id)
                regulation_number = self.regulation_name.regulation_number_for_current_document()
                if regulation_number:
                    self.regulation_number.setText(regulation_number)

            if new_document_id != self._last_document_id:
                self._last_document_id = new_document_id
                self._on_legal_document_changed(clear_section=True)
            elif new_document_id is not None:
                self._populate_legal_sections(document_id=new_document_id)
        finally:
            self._syncing_document_fields = False

    def _on_regulation_number_changed(self, text: str) -> None:
        if self._syncing_document_fields:
            return

        document = self.regulation_name.find_document_by_text(text)
        if document is None:
            if self._last_document_id is not None:
                self._last_document_id = None
                self._on_legal_document_changed(clear_section=True)
            return

        self._syncing_document_fields = True
        try:
            self.regulation_name.set_document_id_without_signal(document.id)
            formatted_number = self.regulation_name.regulation_number_for_current_document()
            if formatted_number:
                self.regulation_number.setText(formatted_number)
            if document.id != self._last_document_id:
                self._last_document_id = document.id
                self._on_legal_document_changed(clear_section=True)
        finally:
            self._syncing_document_fields = False

    def _on_legal_section_changed(self) -> None:
        section_id = self.legal_section.currentData()
        if section_id is None:
            return
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return
        self.provision.setText(self._provision_display_text(self.provision.text(), section_id))

    def _on_legal_document_changed(self, *, clear_section: bool) -> None:
        document_id = self._current_legal_document_id()
        selected_section_id = None if clear_section else self.legal_section.currentData()

        if not clear_section and selected_section_id is not None:
            section = legal_section_service.get_by_id(selected_section_id)
            if section is None or section.legal_document_id != document_id:
                selected_section_id = None

        if self._source_section_id is not None:
            source_section = legal_section_service.get_by_id(self._source_section_id)
            if (
                source_section is None
                or document_id is None
                or source_section.legal_document_id != document_id
            ):
                self._source_section_id = None
                self.source_section_display.clear()

        self._populate_legal_sections(
            selected_id=selected_section_id,
            document_id=document_id,
        )
        if clear_section:
            self.provision.clear()
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

    def _populate_legal_sections(
        self,
        *,
        selected_id: int | None = None,
        document_id: int | None = None,
    ) -> None:
        if document_id is None:
            document_id = self._current_legal_document_id()

        self.legal_section.blockSignals(True)
        self.legal_section.clear()
        self.legal_section.addItem("— bez vazby —", None)

        sections = legal_section_service.list_for_selector(document_id=document_id)
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
        self.legal_section.blockSignals(False)

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
            "regulation_name": self.regulation_name.currentText().strip(),
            "regulation_number": self.regulation_number.text().strip(),
            "provision": self.provision.text().strip(),
            "legal_document_id": self._current_legal_document_id(),
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
