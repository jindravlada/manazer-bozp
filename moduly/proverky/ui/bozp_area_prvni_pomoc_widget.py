"""Pracovní panel oblasti První pomoc."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.widgets.dialog_utils import wrap_in_scroll_area
from moduly.proverky.constants import (
    AREA_PART_NOT_IMPLEMENTED_TEXT,
    FIRST_AID_PARTS,
)


class BozpAreaPrvniPomocWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for part_title in FIRST_AID_PARTS:
            layout.addWidget(self._build_part_section(part_title))

        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap_in_scroll_area(content))

    def _build_part_section(self, title: str) -> QWidget:
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        header = QLabel(title)
        header.setObjectName("SectionTitle")

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)

        placeholder = QLabel(AREA_PART_NOT_IMPLEMENTED_TEXT)
        placeholder.setObjectName("InfoText")
        placeholder.setWordWrap(True)
        panel_layout.addWidget(placeholder)

        section_layout.addWidget(header)
        section_layout.addWidget(panel)
        return container
