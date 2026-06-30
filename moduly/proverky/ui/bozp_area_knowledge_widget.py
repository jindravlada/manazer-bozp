"""Panel oblasti prověrky — seznam sekcí a pracovní karta vybraného uzlu."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.constants import AREA_PANEL_LEFT_WIDTH
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


class BozpAreaKnowledgeWidget(QWidget):
    _SECTION_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, parent=None):
        super().__init__(parent)

        self._sections: list[dict] = []
        self._area_label = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.section_list = QListWidget()
        self.section_list.setAlternatingRowColors(True)
        self.section_list.currentItemChanged.connect(self._on_section_changed)

        self.section_widget = BozpKnowledgeSectionWidget()

        splitter.addWidget(self.section_list)
        splitter.addWidget(self.section_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([AREA_PANEL_LEFT_WIDTH, 1])

        layout.addWidget(splitter)

    def set_knowledge(self, knowledge: dict | None, *, area_label: str = "") -> None:
        self._area_label = area_label.strip()
        self._sections = []
        self.section_list.blockSignals(True)
        self.section_list.clear()
        self.section_list.blockSignals(False)

        if not knowledge:
            self.section_widget.set_section(None)
            return

        self._sections = proverky_knowledge_service.get_active_sections(knowledge)

        self.section_list.blockSignals(True)
        self.section_list.clear()
        for section in self._sections:
            item = QListWidgetItem(str(section.get("nazev") or "—"))
            item.setData(self._SECTION_ROLE, str(section.get("id") or ""))
            self.section_list.addItem(item)
        self.section_list.blockSignals(False)

        if self.section_list.count() > 0:
            self.section_list.setCurrentRow(0)
        else:
            self.section_widget.set_section(None)

    def _section_by_id(self, section_id: str) -> dict | None:
        for section in self._sections:
            if str(section.get("id") or "") == section_id:
                return section
        return None

    def _on_section_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self.section_widget.set_section(None)
            return

        section_id = str(current.data(self._SECTION_ROLE) or "")
        section = self._section_by_id(section_id)
        self.section_widget.set_section(
            section,
            area_label=self._area_label,
            section_label=str(section.get("nazev") or "") if section else "",
        )
