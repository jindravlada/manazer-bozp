"""Panel oblasti prověrky vykreslený ze znalostního JSON."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.widgets.dialog_utils import wrap_in_scroll_area
from moduly.proverky.constants import AREA_PART_NOT_IMPLEMENTED_TEXT
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service


class BozpAreaKnowledgeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap_in_scroll_area(self._content_host))

    def set_knowledge(self, knowledge: dict | None) -> None:
        self._clear_content()

        if not knowledge:
            self._content_layout.addWidget(self._build_info_label("Znalostní soubor oblasti nebyl nalezen."))
            self._content_layout.addStretch()
            return

        sections = proverky_knowledge_service.get_active_sections(knowledge)
        if not sections:
            self._content_layout.addWidget(self._build_info_label("Oblast nemá aktivní sekce."))
            self._content_layout.addStretch()
            return

        for section in sections:
            self._content_layout.addWidget(self._build_section(section))

        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_section(self, section: dict) -> QWidget:
        container = QWidget()
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        title = str(section.get("nazev") or "—").strip() or "—"
        header = QLabel(title)
        header.setObjectName("SectionTitle")

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)

        popis = str(section.get("popis") or "").strip()
        if popis:
            description = QLabel(popis)
            description.setObjectName("InfoText")
            description.setWordWrap(True)
            panel_layout.addWidget(description)

        if proverky_knowledge_service.section_has_content(section):
            panel_layout.addWidget(self._build_info_label("Obsah sekce bude doplněn v další fázi."))
        else:
            panel_layout.addWidget(self._build_info_label(AREA_PART_NOT_IMPLEMENTED_TEXT))

        section_layout.addWidget(header)
        section_layout.addWidget(panel)
        return container

    @staticmethod
    def _build_info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label
