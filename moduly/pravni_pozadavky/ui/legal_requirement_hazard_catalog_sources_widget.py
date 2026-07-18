from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
    HazardCatalogSourceUsage,
    hazard_catalog_legal_requirement_usage_service,
)
from moduly.rizeni_rizik.ui.hazard_library_navigation import open_hazard_library_template

_EMPTY_SOURCES_TEXT = "žádné"
_UNSAVED_SOURCES_TEXT = "Použití bude dostupné až po uložení požadavku."
_SECTION_TITLE = "Zdroje rizik"
_TABLE_HEADERS = ["Název zdroje", "Kategorie", "Revize", "Aktivní"]
_COL_TEMPLATE_ID = 0


class LegalRequirementHazardCatalogSourcesWidget(QWidget):
    def __init__(
        self,
        *,
        requirement_id: int | None = None,
        usage_mode: str = "requirement",
        parent=None,
    ):
        super().__init__(parent)
        self.requirement_id = requirement_id
        self.usage_mode = usage_mode

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._heading = QLabel(_SECTION_TITLE)
        heading_font = QFont(self._heading.font())
        heading_font.setBold(True)
        self._heading.setFont(heading_font)
        self._layout.addWidget(self._heading)

        self._table = QTableWidget()
        self._table.setColumnCount(len(_TABLE_HEADERS) + 1)
        self._table.setHorizontalHeaderLabels([*_TABLE_HEADERS, "ID"])
        self._table.setColumnHidden(len(_TABLE_HEADERS), True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        configure_table_columns(self._table, "legal_requirement_hazard_catalog_sources")
        enable_typed_sorting(self._table)
        self._table.doubleClicked.connect(self._open_selected_source)
        self._layout.addWidget(self._table)

        self._empty_label = QLabel(_EMPTY_SOURCES_TEXT)
        self._layout.addWidget(self._empty_label)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        self.refresh()

    def refresh(self) -> None:
        if self.requirement_id is None:
            self._heading.setText(_SECTION_TITLE)
            self._table.setVisible(False)
            self._empty_label.setText(_UNSAVED_SOURCES_TEXT)
            self._empty_label.setVisible(True)
            return

        sources = self._load_sources()
        self._heading.setText(f"{_SECTION_TITLE} ({len(sources)})")
        self._populate_table(sources)
        self._table.setVisible(bool(sources))
        self._empty_label.setText(_EMPTY_SOURCES_TEXT)
        self._empty_label.setVisible(not sources)

    def _load_sources(self) -> tuple[HazardCatalogSourceUsage, ...]:
        if self.requirement_id is None:
            return ()
        if self.usage_mode == "process":
            return hazard_catalog_legal_requirement_usage_service.list_sources_for_process(
                self.requirement_id,
            )
        return hazard_catalog_legal_requirement_usage_service.list_sources_for_requirement(
            self.requirement_id,
        )

    def _populate_table(self, sources: tuple[HazardCatalogSourceUsage, ...]) -> None:
        with sorting_paused(self._table):
            self._table.setRowCount(len(sources))
            for row_index, source in enumerate(sources):
                stable_id = int(source.template_id)
                values = [
                    (source.name, typed_text(source.name)),
                    (source.category_label, typed_text(source.category_label)),
                    (str(source.version_number), typed_int(source.version_number)),
                    ("Ano" if source.active else "Ne", typed_bool(source.active)),
                ]
                for column_index, (display_text, sort_value) in enumerate(values):
                    item = create_typed_item(display_text, sort_value, stable_id=stable_id)
                    if column_index == 0:
                        item.setData(Qt.ItemDataRole.UserRole, source.template_id)
                    self._table.setItem(row_index, column_index, item)
                id_item = create_typed_item(
                    str(source.template_id),
                    typed_int(source.template_id),
                    stable_id=stable_id,
                )
                self._table.setItem(row_index, len(_TABLE_HEADERS), id_item)

    def _selected_template_id(self) -> int | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self._table.item(selected[0].row(), _COL_TEMPLATE_ID)
        if item is None:
            return None
        template_id = item.data(Qt.ItemDataRole.UserRole)
        return int(template_id) if template_id is not None else None

    def _open_selected_source(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        open_hazard_library_template(self, template_id)

    def visible_sources(self) -> tuple[HazardCatalogSourceUsage, ...]:
        return self._load_sources()
