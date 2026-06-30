"""Pracovní karta znalostního uzlu sekce prověrky."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.widgets.dialog_utils import wrap_in_scroll_area
from moduly.proverky.constants import KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service


class BozpKnowledgeSectionWidget(QWidget):
    """Vykreslí znalostní uzel sekce — popis a tematické bloky z JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap_in_scroll_area(self._content_host))

    def set_section(self, section: dict | None) -> None:
        self._clear_content()

        if not section:
            self._content_layout.addWidget(self._build_info_label("Vyberte sekci v seznamu vlevo."))
            self._content_layout.addStretch()
            return

        self._content_layout.addWidget(self._build_popis_block(section))

        for title, field in proverky_knowledge_service.SECTION_LIST_BLOCKS:
            self._content_layout.addWidget(self._build_list_block(title, section, field))

        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_popis_block(self, section: dict) -> QWidget:
        popis = str(section.get("popis") or "").strip()
        if popis:
            return self._build_block("Popis", self._build_info_label(popis))
        return self._build_block("Popis", self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))

    def _build_list_block(self, title: str, section: dict, field: str) -> QWidget:
        values = section.get(field) or []
        if values:
            return self._build_block(title, self._build_info_label("Obsah bloku bude doplněn v další fázi."))
        return self._build_block(title, self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))

    def _build_block(self, title: str, content: QWidget) -> QWidget:
        container = QWidget()
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(6)

        header = QLabel(title)
        header.setObjectName("SectionTitle")

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(content)

        block_layout.addWidget(header)
        block_layout.addWidget(panel)
        return container

    @staticmethod
    def _build_info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label
