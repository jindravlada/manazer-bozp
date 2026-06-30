from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.constants import (
    AREA_NOT_IMPLEMENTED_TEXT,
    AREA_PANEL_LEFT_WIDTH,
    INSPECTION_AREAS,
    InspectionArea,
)


class BozpInspectionAreasWidget(QWidget):
    """Záložka Kontrolované oblasti — výběr oblasti a placeholder obsahu."""

    _AREA_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.area_list = QListWidget()
        self.area_list.setAlternatingRowColors(True)
        self.area_list.setSpacing(2)

        for area in INSPECTION_AREAS:
            item = QListWidgetItem(area.name)
            item.setData(self._AREA_ROLE, area)
            self.area_list.addItem(item)

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

        self.area_placeholder_label = QLabel(AREA_NOT_IMPLEMENTED_TEXT)
        self.area_placeholder_label.setObjectName("InfoText")
        self.area_placeholder_label.setWordWrap(True)

        detail_layout.addWidget(self.area_title_label)
        detail_layout.addWidget(self.area_description_label)
        detail_layout.addSpacing(8)
        detail_layout.addWidget(self.area_placeholder_label)
        detail_layout.addStretch()

        splitter.addWidget(self.area_list)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([AREA_PANEL_LEFT_WIDTH, 1])

        layout.addWidget(splitter)

        if self.area_list.count() > 0:
            self.area_list.setCurrentRow(0)
        else:
            self._show_empty_detail()

    def _on_area_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._show_empty_detail()
            return

        area = current.data(self._AREA_ROLE)
        if not isinstance(area, InspectionArea):
            self._show_empty_detail()
            return

        self._show_area_detail(area)

    def _show_area_detail(self, area: InspectionArea) -> None:
        self.area_title_label.setText(area.name)
        self.area_description_label.setText(area.description)
        self.area_placeholder_label.setText(AREA_NOT_IMPLEMENTED_TEXT)
        self.area_placeholder_label.setVisible(True)

    def _show_empty_detail(self) -> None:
        self.area_title_label.setText("Kontrolovaná oblast")
        self.area_description_label.setText("Vyberte oblast v seznamu vlevo.")
        self.area_placeholder_label.setVisible(False)
