from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
from core.shared.widgets.entity_links_widget import EntityLinksWidget
from moduly.pravni_pozadavky.ui.legal_requirement_automatic_usage_widget import (
    LegalRequirementAutomaticUsageWidget,
)
from moduly.pravni_pozadavky.ui.legal_requirement_process_link_dialog import (
    LegalRequirementProcessLinkDialog,
)


class LegalRequirementLinksAndUsageWidget(QWidget):
    def __init__(self, requirement_id: int | None = None, parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.automatic_usage_widget = LegalRequirementAutomaticUsageWidget(requirement_id)
        layout.addWidget(self.automatic_usage_widget)

        manual_heading = QLabel("Ruční vazby")
        manual_font = QFont(manual_heading.font())
        manual_font.setBold(True)
        manual_heading.setFont(manual_font)
        layout.addWidget(manual_heading)

        self.links_widget = EntityLinksWidget(
            ENTITY_LEGAL_REQUIREMENT,
            requirement_id,
            link_dialog_class=LegalRequirementProcessLinkDialog,
        )
        layout.addWidget(self.links_widget, 1)

    def refresh(self) -> None:
        self.automatic_usage_widget.refresh()
        if self.links_widget.table is not None:
            self.links_widget.refresh()
