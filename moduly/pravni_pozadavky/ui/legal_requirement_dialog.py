from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_save_cancel_footer,
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.responsibility_role_selector import ResponsibilityRoleSelector
from moduly.pravni_pozadavky.ui.legal_requirement_links_and_usage_widget import (
    LegalRequirementLinksAndUsageWidget,
)
from moduly.pravni_pozadavky.ui.legal_requirement_process_status_widget import (
    LegalRequirementProcessStatusWidget,
)
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_LABELS,
    VALID_COMPLIANCE_STATUSES,
    VALID_PERIODICITIES,
    legal_requirement_merged_target_label,
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
    calculate_next_verification_date,
    legal_requirement_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_display_text_service import (
    legal_section_display_text_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_document_selector import LegalDocumentNameSelector
from moduly.pravni_pozadavky.ui.legal_requirement_children_tab import (
    LegalRequirementChildrenTab,
)
from moduly.pravni_pozadavky.ui.legal_requirement_sanctions_tab import LegalRequirementSanctionsTab
from moduly.pravni_pozadavky.ui.legal_requirement_sources_widget import (
    LegalRequirementSourcesWidget,
    _MISSING_SECTION_TEXT,
    _NO_SOURCE_SELECTED_TEXT,
)


class LegalRequirementDialog(QDialog):
    def __init__(self, parent=None, requirement=None, draft=None, parent_requirement_id=None):
        super().__init__(parent)
        self.requirement = requirement
        self.draft = draft
        self._new_child_parent_id = parent_requirement_id
        self._processing_status: str | None = None
        self._syncing_document_fields = False
        self._last_document_id: int | None = None
        self._loaded_responsible_person_id: int | None = None
        self._syncing_next_verification = False
        self._next_verification_manual_override = False

        if requirement is None and parent_requirement_id is not None:
            window_title = "Nový podřízený proces"
        elif requirement is None:
            window_title = "Řídicí proces"
        else:
            window_title = "Upravit řídicí proces"
        self.setWindowTitle(window_title)
        configure_resizable_form_dialog(self, width=1100, height=780, min_width=900, min_height=600)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), "Řídicí proces")
        self.children_tab: LegalRequirementChildrenTab | None = None
        if self._should_show_children_tab():
            self.children_tab = LegalRequirementChildrenTab(requirement.id)
            self.tabs.addTab(wrap_in_scroll_area(self.children_tab), "Podřízené procesy")
        self.sanctions_tab = LegalRequirementSanctionsTab(
            requirement.id if requirement is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.sanctions_tab), "Sankce")
        self.links_widget = LegalRequirementLinksAndUsageWidget(
            requirement.id if requirement is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.links_widget), "Vazby a použití")
        self.process_status_widget = LegalRequirementProcessStatusWidget(
            requirement.id if requirement is not None else None,
        )
        self.tabs.addTab(wrap_in_scroll_area(self.process_status_widget), "Stav procesu")
        layout.addWidget(self.tabs, 1)
        add_save_cancel_footer(layout, self)

        if requirement is not None:
            self._load_requirement(requirement)
        elif draft is not None:
            self._load_draft(draft)
        elif parent_requirement_id is not None:
            self._load_new_child(parent_requirement_id)
        else:
            self.active_checkbox.setChecked(True)
            self._populate_legal_sections()

    def _main_tab(self) -> QWidget:
        tab = QWidget()
        root_layout = QHBoxLayout(tab)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.merged_into_label = QLabel()
        self.merged_into_label.setWordWrap(True)
        self.merged_into_label.setObjectName("InfoText")
        self.merged_into_label.setVisible(False)

        self.parent_process_caption = QLabel("Nadřazený proces:")
        self.parent_process_label = QLabel()
        self.parent_process_label.setWordWrap(True)

        self.regulation_name = LegalDocumentNameSelector()
        self.regulation_name.setVisible(False)
        self.process_title = QLineEdit()
        self.regulation_number = QLineEdit()
        self.regulation_number.setVisible(False)
        self.provision = QLineEdit()
        self.provision.setVisible(False)
        self.legal_section = QComboBox()
        self.legal_section.setVisible(False)
        self.sources_widget = LegalRequirementSourcesWidget()
        self.sources_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.area = QLineEdit()
        self.requirement_summary = QTextEdit()
        self.requirement_summary.setMinimumHeight(48)
        self.requirement_summary.setMaximumHeight(64)
        self.requirement_summary.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.organization_impact = QTextEdit()
        self.organization_impact.setMinimumHeight(48)
        self.organization_impact.setMaximumHeight(64)
        self.organization_impact.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.responsible_role = ResponsibilityRoleSelector()
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

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.merged_into_label)

        identification_group = QGroupBox("Identifikace procesu")
        identification_form = QFormLayout(identification_group)
        identification_form.addRow(self.parent_process_caption, self.parent_process_label)
        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.addWidget(self.process_title, 1)
        title_row_layout.addWidget(
            self.active_checkbox,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        identification_form.addRow("Řídicí proces:", title_row)
        self._set_parent_process_display(None)
        left_layout.addWidget(identification_group, 0)

        sources_group = QGroupBox("Právní podklady")
        sources_layout = QVBoxLayout(sources_group)
        sources_layout.setContentsMargins(8, 8, 8, 8)
        sources_layout.addWidget(self.sources_widget, 1)
        left_layout.addWidget(sources_group, 1)

        process_group = QGroupBox("Popis procesu")
        process_form = QFormLayout(process_group)
        process_form.addRow("Způsob plnění:", self.requirement_summary)
        process_form.addRow("Metodika plnění:", self.organization_impact)
        left_layout.addWidget(process_group, 0)

        management_group = QGroupBox("Správa procesu")
        management_form = QFormLayout(management_group)
        management_form.addRow("Vlastník procesu:", self.responsible_role)
        management_form.addRow("Periodicita ověření:", self.periodicity)
        management_form.addRow("Poslední ověření:", self.last_verification)
        management_form.addRow("Další ověření:", self.next_verification)
        management_form.addRow("Stav plnění:", self.compliance_status)
        note_block = QWidget()
        note_layout = QVBoxLayout(note_block)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.addWidget(QLabel("Poznámka:"))
        note_layout.addWidget(self.note)
        management_form.addRow(note_block)
        left_layout.addWidget(management_group, 0)

        left_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.regulation_name.document_changed.connect(self._on_regulation_name_changed)
        self.regulation_number.textChanged.connect(self._on_regulation_number_changed)
        self.legal_section.currentIndexChanged.connect(self._on_legal_section_changed)
        self.sources_widget.tree.itemSelectionChanged.connect(self._on_source_selection_changed)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        provision_text_group = QGroupBox("Znění právního podkladu")
        provision_text_layout = QVBoxLayout(provision_text_group)
        self.provision_text_header = QLabel()
        self.provision_text_header.setWordWrap(True)
        self.provision_text_separator = QFrame()
        self.provision_text_separator.setFrameShape(QFrame.Shape.HLine)
        self.provision_text_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.provision_text_view = QTextEdit()
        self.provision_text_view.setReadOnly(True)
        self.provision_text_view.setMinimumWidth(320)
        provision_text_layout.addWidget(self.provision_text_header)
        provision_text_layout.addWidget(self.provision_text_separator)
        provision_text_layout.addWidget(self.provision_text_view, 1)

        self.process_inputs_view = QTextEdit()
        self.process_inputs_view.setMinimumHeight(70)
        inputs_group = QGroupBox("Vstupy procesu")
        inputs_layout = QVBoxLayout(inputs_group)
        inputs_layout.addWidget(self.process_inputs_view)

        self.process_outputs_view = QTextEdit()
        self.process_outputs_view.setMinimumHeight(70)
        outputs_group = QGroupBox("Výstupy procesu")
        outputs_layout = QVBoxLayout(outputs_group)
        outputs_layout.addWidget(self.process_outputs_view)

        right_layout.addWidget(provision_text_group, 2)
        right_layout.addWidget(inputs_group, 1)
        right_layout.addWidget(outputs_group, 1)
        right_widget.setMinimumWidth(320)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter)

        self.periodicity.currentIndexChanged.connect(self._on_verification_schedule_changed)
        self.last_verification.dateChanged.connect(self._on_verification_schedule_changed)
        self.next_verification.dateChanged.connect(self._on_next_verification_manually_changed)

        self._display_section_text(self.sources_widget.selected_section_id())
        return tab

    def _should_show_children_tab(self) -> bool:
        return (
            self.requirement is not None
            and self.requirement.id is not None
            and self.requirement.parent_requirement_id is None
        )

    def _set_parent_process_display(self, text: str | None) -> None:
        visible = bool(text)
        self.parent_process_caption.setVisible(visible)
        self.parent_process_label.setVisible(visible)
        self.parent_process_label.setText(text or "")

    def _load_parent_process_display(self, requirement) -> None:
        if requirement.parent_requirement_id is None:
            self._set_parent_process_display(None)
            return

        parent = legal_requirement_service.get_by_id(requirement.parent_requirement_id)
        if parent is None:
            self._set_parent_process_display(None)
            return

        self._set_parent_process_display(legal_requirement_merged_target_label(parent))

    def _load_new_child(self, parent_requirement_id: int) -> None:
        parent = legal_requirement_service.get_by_id(parent_requirement_id)
        if parent is not None:
            self._set_parent_process_display(legal_requirement_merged_target_label(parent))
        else:
            self._set_parent_process_display(None)
        self.process_title.clear()
        self.active_checkbox.setChecked(True)
        self._populate_legal_sections()

    def accept(self) -> None:
        if not self.process_title.text().strip():
            QMessageBox.warning(
                self,
                "Řídicí proces",
                "Název řídicího procesu musí být vyplněn.",
            )
            return
        super().accept()

    def _load_requirement(self, requirement) -> None:
        self._loaded_responsible_person_id = requirement.responsible_person_id
        self.process_title.setText(requirement.title or "")
        self._load_parent_process_display(requirement)
        if requirement.merged_into_requirement_id is not None:
            target = legal_requirement_service.get_by_id(requirement.merged_into_requirement_id)
            if target is not None:
                self.merged_into_label.setText(
                    "Tento proces byl sloučen do:\n"
                    f"{legal_requirement_merged_target_label(target)}",
                )
                self.merged_into_label.setVisible(True)
            else:
                self.merged_into_label.setVisible(False)
        else:
            self.merged_into_label.setVisible(False)

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
        self.process_inputs_view.setPlainText(requirement.process_inputs)
        self.process_outputs_view.setPlainText(requirement.process_outputs)
        self.responsible_role.set_role_id(
            requirement.responsible_role_id,
            requirement.responsible_role_name,
        )
        self._set_combo_value(self.periodicity, requirement.verification_periodicity)
        self._load_verification_dates(
            last_verification_date=requirement.last_verification_date,
            next_verification_date=requirement.next_verification_date,
            periodicity=requirement.verification_periodicity,
        )
        self._set_combo_value(self.compliance_status, requirement.compliance_status)
        self.note.setPlainText(requirement.note)
        self.active_checkbox.setChecked(requirement.active)
        self._processing_status = requirement.processing_status
        source_section_ids = legal_requirement_service.list_source_section_ids_for_requirement(
            requirement.id,
        )
        self.sources_widget.load_section_ids(source_section_ids)
        self._refresh_provision_text_panel()

    def _load_draft(self, draft) -> None:
        self._loaded_responsible_person_id = None
        self.process_title.clear()
        self._set_parent_process_display(None)
        self.merged_into_label.setVisible(False)
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
        self._processing_status = draft.processing_status
        if draft.source_section_id is not None:
            self.sources_widget.load_section_ids([draft.source_section_id])
        else:
            self.sources_widget.load_section_ids([])
        self._refresh_provision_text_panel()

    def _on_source_selection_changed(self) -> None:
        self._display_section_text(self.sources_widget.selected_section_id())

    def _refresh_provision_text_panel(self) -> None:
        if self.sources_widget.get_section_ids():
            self.sources_widget.select_first_row()
        self._display_section_text(self.sources_widget.selected_section_id())

    def _display_section_text(self, section_id: int | None) -> None:
        if section_id is None:
            self.provision_text_header.clear()
            self.provision_text_header.setVisible(False)
            self.provision_text_separator.setVisible(False)
            self.provision_text_view.setPlainText(_NO_SOURCE_SELECTED_TEXT)
            return

        header = self._provision_header_for_section(section_id)
        self.provision_text_header.setText(header)
        self.provision_text_header.setVisible(bool(header))
        self.provision_text_separator.setVisible(bool(header))

        display_text = legal_section_display_text_service.compose(section_id)
        if not display_text:
            self.provision_text_view.setPlainText(_MISSING_SECTION_TEXT)
            return

        self.provision_text_view.setPlainText(display_text)

    def _provision_header_for_section(self, section_id: int) -> str:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return ""

        document = legal_document_service.get_by_id(section.legal_document_id)
        regulation_number = legal_document_regulation_number(document) if document is not None else ""
        sections_by_id = legal_section_service.build_sections_map([section])
        provision_label = legal_section_provision_label(section, sections_by_id=sections_by_id)
        if not provision_label:
            provision_label = f"Ustanovení #{section.id}"

        if regulation_number and provision_label:
            return f"{regulation_number}\n{provision_label}"
        return regulation_number or provision_label

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

        self._populate_legal_sections(
            selected_id=selected_section_id,
            document_id=document_id,
        )
        if clear_section:
            self.provision.clear()

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

    def _load_verification_dates(
        self,
        *,
        last_verification_date,
        next_verification_date,
        periodicity: str,
    ) -> None:
        self._syncing_next_verification = True
        try:
            self.last_verification.set_date_value(last_verification_date)
            self.next_verification.set_date_value(next_verification_date)
        finally:
            self._syncing_next_verification = False
        self._next_verification_manual_override = self._is_manual_next_verification(
            last_verification_date,
            periodicity,
            next_verification_date,
        )

    def _is_manual_next_verification(
        self,
        last_verification_date,
        periodicity: str,
        next_verification_date,
    ) -> bool:
        if next_verification_date is None:
            return False
        if last_verification_date is None or not periodicity:
            return True
        suggested = calculate_next_verification_date(last_verification_date, periodicity)
        if suggested is None:
            return True
        return next_verification_date != suggested

    def _on_verification_schedule_changed(self) -> None:
        if self._syncing_next_verification:
            return
        self._apply_suggested_next_verification(force=True)

    def _on_next_verification_manually_changed(self) -> None:
        if self._syncing_next_verification:
            return
        self._next_verification_manual_override = True

    def _apply_suggested_next_verification(self, *, force: bool = False) -> None:
        if not force and self._next_verification_manual_override:
            return

        last_verification_date = self.last_verification.get_date()
        periodicity = self.periodicity.currentData() or ""
        if last_verification_date is None or not periodicity:
            return

        suggested = calculate_next_verification_date(last_verification_date, periodicity)
        if suggested is None:
            return

        self._syncing_next_verification = True
        try:
            self.next_verification.set_date_value(suggested)
            if force:
                self._next_verification_manual_override = False
        finally:
            self._syncing_next_verification = False

    def get_data(self) -> dict:
        periodicity = self.periodicity.currentData() or ""
        compliance_status = self.compliance_status.currentData() or ""
        if periodicity not in VALID_PERIODICITIES:
            periodicity = ""
        if compliance_status not in VALID_COMPLIANCE_STATUSES:
            compliance_status = ""

        source_section_ids = self.sources_widget.get_section_ids()
        return {
            "title": self.process_title.text().strip(),
            "regulation_name": self.regulation_name.currentText().strip(),
            "regulation_number": self.regulation_number.text().strip(),
            "provision": self.provision.text().strip(),
            "legal_document_id": self._current_legal_document_id(),
            "legal_section_id": self.legal_section.currentData(),
            "source_section_id": source_section_ids[0] if source_section_ids else None,
            "source_section_ids": source_section_ids,
            "area": self.area.text().strip(),
            "requirement_summary": self.requirement_summary.toPlainText().strip(),
            "organization_impact": self.organization_impact.toPlainText().strip(),
            "process_inputs": self.process_inputs_view.toPlainText().strip(),
            "process_outputs": self.process_outputs_view.toPlainText().strip(),
            "responsible_person_id": self._loaded_responsible_person_id,
            "responsible_role_id": self.responsible_role.current_role_id(),
            "verification_periodicity": periodicity,
            "last_verification_date": self.last_verification.get_date(),
            "next_verification_date": self.next_verification.get_date(),
            "compliance_status": compliance_status,
            "processing_status": self._processing_status or "",
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
