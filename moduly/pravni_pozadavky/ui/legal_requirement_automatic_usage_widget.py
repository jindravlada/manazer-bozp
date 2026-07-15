from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.pravni_pozadavky.sluzby.legal_requirement_usage_service import (
    legal_requirement_usage_service,
)
from moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget import (
    LegalRequirementHazardCatalogSourcesWidget,
)

_EMPTY_USAGE_TEXT = "žádné"
_UNSAVED_USAGE_TEXT = "Použití bude dostupné až po uložení procesu."


class LegalRequirementAutomaticUsageWidget(QWidget):
    def __init__(
        self,
        requirement_id: int | None = None,
        *,
        is_process: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.requirement_id = requirement_id
        self.is_process = is_process

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Automatické použití procesu")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading.setFont(heading_font)
        self._layout.addWidget(heading)

        self._process_hazard_sources_widget: LegalRequirementHazardCatalogSourcesWidget | None = None
        if self.is_process:
            self._process_hazard_sources_widget = LegalRequirementHazardCatalogSourcesWidget(
                requirement_id=requirement_id,
                usage_mode="process",
            )
            self._layout.addWidget(self._process_hazard_sources_widget)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        if self._process_hazard_sources_widget is not None:
            self._process_hazard_sources_widget.set_requirement_id(requirement_id)
        self.refresh()

    def refresh(self) -> None:
        preserved_count = 2 if self._process_hazard_sources_widget is not None else 1
        while self._layout.count() > preserved_count:
            item = self._layout.takeAt(preserved_count)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._process_hazard_sources_widget is not None:
            self._process_hazard_sources_widget.refresh()

        if self.requirement_id is None:
            self._layout.addWidget(QLabel(_UNSAVED_USAGE_TEXT))
            return

        usage = legal_requirement_usage_service.get_usage(self.requirement_id)

        for warning in usage.warnings:
            warning_label = QLabel(warning)
            warning_label.setObjectName("WarningText")
            warning_label.setWordWrap(True)
            self._layout.addWidget(warning_label)

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
        self._add_usage_section(
            "Oblasti prověrek",
            [item.display_label for item in usage.inspection_areas],
        )
        self._add_usage_section(
            "Kontrolní otázky prověrek",
            [item.text for item in usage.inspection_questions],
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
