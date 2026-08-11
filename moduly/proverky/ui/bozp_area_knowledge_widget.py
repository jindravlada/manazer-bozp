"""Panel oblasti prověrky — pracovní karta vybraného znalostního uzlu."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from moduly.proverky.constants import VERIFICATION_TYPE_DOCUMENTATION
from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


class BozpAreaKnowledgeWidget(QWidget):
    def __init__(self, parent=None, *, verification_filter: str = VERIFICATION_TYPE_DOCUMENTATION):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.section_widget = BozpKnowledgeSectionWidget()
        self.section_widget.set_verification_filter(verification_filter)
        layout.addWidget(self.section_widget)

    def show_section(
        self,
        section: dict | None,
        *,
        area_id: str = "",
        area_label: str = "",
        section_label: str = "",
    ) -> None:
        self.section_widget.set_section(
            section,
            area_id=area_id,
            area_label=area_label,
            section_label=section_label,
        )

    def clear_section(self) -> None:
        self.section_widget.set_section(None)

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.section_widget.set_inspection_id(inspection_id)

    def set_verification_filter(self, verification_type: str) -> None:
        self.section_widget.set_verification_filter(verification_type)

    def set_on_finding_saved(self, callback) -> None:
        self.section_widget.set_on_finding_saved(callback)

    def set_deferred_edits(self, deferred_edits) -> None:
        self.section_widget.set_deferred_edits(deferred_edits)

    def set_on_deferred_dirty(self, callback) -> None:
        self.section_widget.set_on_deferred_dirty(callback)

    def refresh_findings_display(self) -> None:
        self.section_widget.refresh()
