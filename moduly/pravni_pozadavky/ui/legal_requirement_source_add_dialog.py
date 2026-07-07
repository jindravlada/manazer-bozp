from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.constants import legal_section_provision_label
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_document_selector import LegalDocumentNameSelector


class LegalRequirementSourceAddDialog(QDialog):
    def __init__(self, parent=None, *, excluded_section_ids: set[int] | None = None):
        super().__init__(parent)
        self._excluded_section_ids = excluded_section_ids or set()
        self._selected_section_id: int | None = None

        self.setWindowTitle("Přidat právní podklad")
        configure_resizable_form_dialog(self, width=520, height=220, min_width=420, min_height=180)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.document_selector = LegalDocumentNameSelector()
        self.section_combo = QComboBox()
        self.section_combo.addItem("— vyberte ustanovení —", None)

        form.addRow("Právní předpis:", self.document_selector)
        form.addRow("Ustanovení:", self.section_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.document_selector.document_changed.connect(self._on_document_changed)
        self._on_document_changed()

    def selected_section_id(self) -> int | None:
        return self._selected_section_id

    def _on_document_changed(self) -> None:
        document_id = self.document_selector.current_document_id()
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItem("— vyberte ustanovení —", None)

        sections = legal_section_service.list_for_selector(document_id=document_id)
        sections_by_id = legal_section_service.build_sections_map(sections)
        for section in sections:
            if section.id in self._excluded_section_ids:
                continue
            label = legal_section_provision_label(section, sections_by_id=sections_by_id)
            if not label:
                label = f"Ustanovení #{section.id}"
            self.section_combo.addItem(label, section.id)

        self.section_combo.blockSignals(False)

    def _accept(self) -> None:
        section_id = self.section_combo.currentData()
        if section_id is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Právní podklad", "Vyberte ustanovení předpisu.")
            return
        self._selected_section_id = section_id
        self.accept()
