from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.constants import AREA_NOT_IMPLEMENTED_TEXT
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KnowledgeTreeNode,
    proverky_knowledge_service,
)
from moduly.proverky.ui.bozp_area_knowledge_widget import BozpAreaKnowledgeWidget
from moduly.proverky.ui.bozp_knowledge_tree_widget import BozpKnowledgeTreeWidget


class BozpInspectionAreasWidget(QWidget):
    """Záložka Kontrolované oblasti — znalostní strom a pracovní karta."""

    _PAGE_HINT = 0
    _PAGE_PLACEHOLDER = 1
    _PAGE_KNOWLEDGE = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()

        self.knowledge_tree = BozpKnowledgeTreeWidget()
        self.knowledge_tree.section_selected.connect(self._on_section_selected)
        self.knowledge_tree.area_selected.connect(self._on_area_selected)

        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("ModulePanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        self.area_title_label = QLabel()
        self.area_title_label.setObjectName("SectionTitle")
        self.area_title_label.setWordWrap(True)

        self.area_description_label = QLabel()
        self.area_description_label.setObjectName("InfoText")
        self.area_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_hint_page())
        self.content_stack.addWidget(self._build_placeholder_page())
        self.knowledge_widget = BozpAreaKnowledgeWidget()
        self.content_stack.addWidget(self.knowledge_widget)

        detail_layout.addWidget(self.area_title_label)
        detail_layout.addWidget(self.area_description_label)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(self.content_stack, 1)

        splitter.addWidget(self.knowledge_tree)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        self.reload_areas()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.knowledge_widget.set_inspection_id(inspection_id)

    def set_on_finding_saved(self, callback) -> None:
        self.knowledge_widget.set_on_finding_saved(callback)

    def refresh_findings_display(self) -> None:
        self.knowledge_widget.refresh_findings_display()

    def reload_areas(self) -> None:
        self.knowledge_tree.reload_tree()
        self._show_hint()

    def _build_hint_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Vyberte sekci ve stromu znalostí vlevo.")
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(AREA_NOT_IMPLEMENTED_TEXT)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _show_hint(self) -> None:
        self.area_title_label.setText("Kontrolované oblasti")
        self.area_description_label.setText("Vyberte sekci ve stromu znalostí vlevo.")
        self.area_description_label.setVisible(True)
        self.knowledge_widget.clear_section()
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_area_selected(self, node: KnowledgeTreeNode) -> None:
        area_def = proverky_knowledge_service.get_area_by_id(node.area_id)

        self.area_title_label.setText(node.area_label)
        if area_def and area_def.popis:
            self.area_description_label.setText(area_def.popis)
            self.area_description_label.setVisible(True)
        else:
            self.area_description_label.setText("Vyberte sekci pod touto oblastí.")
            self.area_description_label.setVisible(True)

        self.knowledge_widget.clear_section()
        if area_def and area_def.has_knowledge_file and node.children:
            self.content_stack.setCurrentIndex(self._PAGE_HINT)
        else:
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

    def _on_section_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        section = node.section
        if section is None:
            self._show_hint()
            return

        self.area_title_label.setText(node.area_label)
        section_label = str(section.get("nazev") or "").strip()
        section_popis = str(section.get("popis") or "").strip()
        if section_popis:
            self.area_description_label.setText(section_popis)
            self.area_description_label.setVisible(True)
        else:
            self.area_description_label.setVisible(False)

        self.knowledge_widget.show_section(
            section,
            area_id=node.area_id,
            area_label=node.area_label,
            section_label=section_label,
        )
        self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
