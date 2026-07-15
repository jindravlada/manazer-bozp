from PySide6.QtWidgets import QVBoxLayout, QWidget

from moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget import (
    LegalRequirementHazardCatalogSourcesWidget,
)


class LegalDocumentHazardCatalogSourcesTab(QWidget):
    """Zdroje rizik napojené přímo na právní předpis (R19b)."""

    def __init__(self, document_id: int | None = None, parent=None):
        super().__init__(parent)
        self.document_id = document_id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sources_widget = _DocumentHazardCatalogSourcesWidget(
            document_id=document_id,
        )
        layout.addWidget(self.sources_widget)

    def refresh(self) -> None:
        self.sources_widget.set_document_id(self.document_id)
        self.sources_widget.refresh()


class _DocumentHazardCatalogSourcesWidget(LegalRequirementHazardCatalogSourcesWidget):
    def __init__(self, *, document_id: int | None = None, parent=None):
        self._document_id = document_id
        super().__init__(requirement_id=document_id, usage_mode="document", parent=parent)

    def set_document_id(self, document_id: int | None) -> None:
        self._document_id = document_id
        self.set_requirement_id(document_id)

    def _load_sources(self):
        from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
            hazard_catalog_legal_requirement_usage_service,
        )

        if self._document_id is None:
            return ()
        return hazard_catalog_legal_requirement_usage_service.list_sources_for_document(
            self._document_id,
        )
