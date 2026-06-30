from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.constants import AREA_NOT_IMPLEMENTED_TEXT, AREA_PANEL_LEFT_WIDTH
from moduly.proverky.sluzby.proverky_knowledge_service import (
    InspectionAreaDefinition,
    proverky_knowledge_service,
)
from moduly.proverky.ui.bozp_area_knowledge_widget import BozpAreaKnowledgeWidget


class BozpInspectionAreasWidget(QWidget):
    """Záložka Kontrolované oblasti — výběr oblasti a obsah vpravo."""

    _AREA_ROLE = Qt.ItemDataRole.UserRole
    _PAGE_PLACEHOLDER = 0
    _PAGE_KNOWLEDGE = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._areas: list[InspectionAreaDefinition] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.area_list = QListWidget()
        self.area_list.setAlternatingRowColors(True)
        self.area_list.currentItemChanged.connect(self._on_area_changed)

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
        self.content_stack.addWidget(self._build_placeholder_page())
        self.knowledge_widget = BozpAreaKnowledgeWidget()
        self.content_stack.addWidget(self.knowledge_widget)

        detail_layout.addWidget(self.area_title_label)
        detail_layout.addWidget(self.area_description_label)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(self.content_stack, 1)

        splitter.addWidget(self.area_list)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([AREA_PANEL_LEFT_WIDTH, 1])

        layout.addWidget(splitter)

        self.reload_areas()

    def reload_areas(self) -> None:
        self._areas = proverky_knowledge_service.get_areas()

        self.area_list.blockSignals(True)
        self.area_list.clear()
        for area in self._areas:
            item = QListWidgetItem(area.nazev)
            item.setData(self._AREA_ROLE, area.id)
            self.area_list.addItem(item)
        self.area_list.blockSignals(False)

        if self.area_list.count() > 0:
            self.area_list.setCurrentRow(0)
        else:
            self._show_empty_detail()

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

    def _area_by_id(self, area_id: str) -> InspectionAreaDefinition | None:
        for area in self._areas:
            if area.id == area_id:
                return area
        return None

    def _on_area_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._show_empty_detail()
            return

        area_id = current.data(self._AREA_ROLE)
        area = self._area_by_id(str(area_id or ""))
        if area is None:
            self._show_empty_detail()
            return

        self._show_area_detail(area)

    def _show_area_detail(self, area: InspectionAreaDefinition) -> None:
        self.area_title_label.setText(area.nazev)
        self.area_description_label.setText(area.popis)
        self.area_description_label.setVisible(bool(area.popis))

        if area.has_knowledge_file:
            knowledge = proverky_knowledge_service.load_area_knowledge(area)
            self.knowledge_widget.set_knowledge(knowledge, area_label=area.nazev)
            self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
        else:
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

    def _show_empty_detail(self) -> None:
        self.area_title_label.setText("Kontrolovaná oblast")
        self.area_description_label.setText("Vyberte oblast v seznamu vlevo.")
        self.area_description_label.setVisible(True)
        self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)
