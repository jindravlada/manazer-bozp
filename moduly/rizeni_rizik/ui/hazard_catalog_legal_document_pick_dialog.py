"""Dialog výběru právního předpisu pro AI návrhovou vazbu (R20f.5)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.ui.legal_document_selector import LegalDocumentNameSelector


class HazardCatalogLegalDocumentPickDialog(QDialog):
    """Výběr předpisu z registru s našeptávačem (bez celoobrazovkového seznamu)."""

    def __init__(
        self,
        parent=None,
        *,
        ai_reference: str = "",
        initial_document_id: int | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Výběr právního předpisu")
        self.resize(520, 360)
        self._selected_document_id: int | None = initial_document_id

        root = QVBoxLayout(self)

        proposal_box = QGroupBox("Návrh AI")
        proposal_layout = QVBoxLayout(proposal_box)
        self.ai_reference_label = QLabel(ai_reference.strip() or "—")
        self.ai_reference_label.setWordWrap(True)
        proposal_layout.addWidget(self.ai_reference_label)
        root.addWidget(proposal_box)

        search_box = QGroupBox("Vyhledat předpis")
        search_layout = QFormLayout(search_box)
        search_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow,
        )
        self.selector = LegalDocumentNameSelector(self)
        if self.selector.lineEdit() is not None:
            self.selector.lineEdit().setPlaceholderText(
                "Začněte psát název, číslo nebo zkratku…",
            )
        self.selector.document_changed.connect(self._refresh_selected_label)
        self.selector.currentTextChanged.connect(self._refresh_selected_label)
        search_layout.addRow("Předpis:", self.selector)
        root.addWidget(search_box)

        selected_box = QGroupBox("Vybraný předpis")
        selected_layout = QVBoxLayout(selected_box)
        self.selected_label = QLabel("—")
        self.selected_label.setWordWrap(True)
        selected_layout.addWidget(self.selected_label)
        root.addWidget(selected_box)

        buttons = create_save_cancel_box(self)
        use_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if use_button is not None:
            use_button.setText("Použít")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if initial_document_id is not None:
            self.selector.reload(selected_id=initial_document_id)
            self.selector.set_document_id(initial_document_id)
        self._refresh_selected_label()

    def selected_document_id(self) -> int | None:
        return self._selected_document_id

    def selected_document_title(self) -> str:
        document_id = self._selected_document_id
        if document_id is None:
            return ""
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            return ""
        return (document.title or "").strip()

    def accept(self) -> None:
        self._selected_document_id = self.selector.current_document_id()
        if self._selected_document_id is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Vyberte předpis z našeptávače.",
            )
            return
        super().accept()

    def _refresh_selected_label(self) -> None:
        document = self.selector.current_document()
        if document is None:
            self.selected_label.setText("—")
            self._selected_document_id = None
            return
        title = (document.title or "").strip() or f"Předpis #{document.id}"
        self.selected_label.setText(title)
        self._selected_document_id = int(document.id)
