from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.sluzby.legal_requirement_usage_service import (
    legal_requirement_usage_service,
)

_EMPTY_USAGE_TEXT = "žádné"
_UNSAVED_USAGE_TEXT = "Použití bude dostupné až po uložení procesu."


class LegalRequirementAutomaticUsageWidget(QWidget):
    def __init__(self, requirement_id: int | None = None, parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Automatické použití procesu")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading.setFont(heading_font)
        self._layout.addWidget(heading)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        self.refresh()

    def refresh(self) -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self.requirement_id is None:
            self._layout.addWidget(QLabel(_UNSAVED_USAGE_TEXT))
            return

        usage = legal_requirement_usage_service.get_usage(self.requirement_id)
        self._add_usage_section(
            "Právní podklady",
            [item.label for item in usage.legal_provisions],
        )
        self._add_usage_section(
            "Auditní oblasti",
            [item.display_label for item in usage.audit_areas],
        )
        self._add_usage_section(
            "Auditní tvrzení",
            [item.text for item in usage.audit_assertions],
        )
        self._layout.addStretch()

    def _add_usage_section(self, title: str, items: list[str]) -> None:
        section_heading = QLabel(title)
        section_font = QFont(section_heading.font())
        section_font.setBold(True)
        section_heading.setFont(section_font)
        self._layout.addWidget(section_heading)

        if items:
            for text in items:
                self._layout.addWidget(QLabel(f"• {text}"))
        else:
            self._layout.addWidget(QLabel(_EMPTY_USAGE_TEXT))
