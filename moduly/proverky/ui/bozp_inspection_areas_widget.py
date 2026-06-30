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

from moduly.proverky.constants import (
    AREA_CODE_PRVNI_POMOC,
    AREA_NOT_IMPLEMENTED_TEXT,
    AREA_PANEL_LEFT_WIDTH,
    INSPECTION_AREAS,
    InspectionArea,
)
from moduly.proverky.ui.bozp_area_prvni_pomoc_widget import BozpAreaPrvniPomocWidget


class BozpInspectionAreasWidget(QWidget):
    """Záložka Kontrolované oblasti — výběr oblasti a obsah vpravo."""

    _AREA_ROLE = Qt.ItemDataRole.UserRole
    _PAGE_PLACEHOLDER = 0
    _PAGE_PRVNI_POMOC = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.area_list = QListWidget()
        self.area_list.setAlternatingRowColors(True)

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

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_placeholder_page())
        self.content_stack.addWidget(BozpAreaPrvniPomocWidget())

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
        self.area_description_label.setVisible(True)

        if area.code == AREA_CODE_PRVNI_POMOC:
            self.content_stack.setCurrentIndex(self._PAGE_PRVNI_POMOC)
        else:
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

    def _show_empty_detail(self) -> None:
        self.area_title_label.setText("Kontrolovaná oblast")
        self.area_description_label.setText("Vyberte oblast v seznamu vlevo.")
        self.area_description_label.setVisible(True)
        self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)
