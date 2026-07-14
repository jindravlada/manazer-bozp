from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    INVENTORY_COL_ACTIVE,
    INVENTORY_COL_DESCRIPTION,
    INVENTORY_COL_ID,
    INVENTORY_COL_NAME,
    INVENTORY_COLUMN_COUNT,
    INVENTORY_INTRO_TEXT,
    INVENTORY_ITEM_DIALOG_TITLE,
    INVENTORY_TABLE_HEADERS,
    WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
    WORKPLACE_ANALYSIS_SELECT_ITEM,
    format_inventory_item_display_name,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import hazard_inventory_item_service
from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import hazard_inventory_relation_service
from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog
from moduly.rizeni_rizik.ui.hazard_inventory_analysis_widget import HazardInventoryAnalysisWidget
from moduly.rizeni_rizik.ui.hazard_inventory_item_dialog import HazardInventoryItemDialog


class HazardInventoryWidget(QWidget):
    def __init__(self, parent=None, on_event_saved=None):
        super().__init__(parent)

        self._on_event_saved = on_event_saved

        self._identification_id: int | None = None
        self._read_only = False
        self._current_category = HAZARD_INVENTORY_CATEGORIES[0]
        self._selected_item_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(INVENTORY_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.add_event_btn = QPushButton("Přidat nežádoucí událost")
        self.toolbar.addWidget(self.add_btn)
        self.toolbar.addWidget(self.edit_btn)
        self.toolbar.addWidget(self.activate_btn)
        self.toolbar.addWidget(self.deactivate_btn)
        self.toolbar.addWidget(self.add_event_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setMinimumWidth(240)
        splitter.addWidget(self.category_list)

        right_host = QWidget()
        right_layout = QVBoxLayout(right_host)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(INVENTORY_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(INVENTORY_TABLE_HEADERS)
        self.table.setColumnHidden(INVENTORY_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_inventory_items")
        right_layout.addWidget(self.table, 2)

        self.analysis_widget = HazardInventoryAnalysisWidget(on_changed=self._load_table)
        right_layout.addWidget(self.analysis_widget, 3)

        splitter.addWidget(right_host)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.edit_btn.clicked.connect(self.edit_selected_item)
        self.activate_btn.clicked.connect(self.activate_selected_item)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_item)
        self.add_event_btn.clicked.connect(self.add_event_for_selected_item)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
        self.table.itemSelectionChanged.connect(self._on_item_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_item)

        self._populate_categories()
        self.set_identification(None, read_only=False)

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._identification_id = identification_id
        self._read_only = read_only
        self._selected_item_id = None
        self._set_actions_enabled(not read_only and identification_id is not None)
        self.analysis_widget.set_source_item(
            None,
            identification_id=identification_id,
            read_only=read_only,
        )
        self.refresh()

    def refresh(self) -> None:
        self._populate_categories()
        self._load_table()
        self._sync_analysis_selection()

    def add_item(self) -> None:
        if not self._ensure_editable():
            return

        dialog = HazardInventoryItemDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_category=self._current_category,
        )
        if dialog.exec():
            self.refresh()

    def edit_selected_item(self) -> None:
        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return

        dialog = HazardInventoryItemDialog(
            self,
            hazard_identification_id=self._identification_id,
            item=item,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()

    def activate_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return
        if item.active:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Položka je již aktivní.")
            return

        from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import HazardInventoryItemError

        try:
            hazard_inventory_item_service.activate_item(item.id)
        except HazardInventoryItemError as error:
            QMessageBox.warning(self, INVENTORY_ITEM_DIALOG_TITLE, str(error))
            return
        self.refresh()

    def deactivate_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, WORKPLACE_ANALYSIS_SELECT_ITEM)
            return
        if not item.active:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Položka je již neaktivní.")
            return

        hazard_inventory_item_service.deactivate_item(item.id)
        self.refresh()

    def add_event_for_selected_item(self) -> None:
        if not self._ensure_editable():
            return

        item = self._selected_item()
        if item is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                WORKPLACE_ANALYSIS_SELECT_ITEM,
            )
            return

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_inventory_item_id=item.id,
        )
        if dialog.exec():
            self._notify_event_saved()
            self.refresh()

    def _notify_event_saved(self) -> None:
        if self._on_event_saved is not None:
            self._on_event_saved()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                INVENTORY_ITEM_DIALOG_TITLE,
                WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
            )
            return False
        return True

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
            self.add_event_btn,
        ):
            button.setEnabled(enabled)

    def _populate_categories(self) -> None:
        counts = (
            hazard_inventory_item_service.count_active_by_category(self._identification_id)
            if self._identification_id is not None
            else {category: 0 for category in HAZARD_INVENTORY_CATEGORIES}
        )

        selected_category = self._current_category
        self.category_list.blockSignals(True)
        self.category_list.clear()
        for category in HAZARD_INVENTORY_CATEGORIES:
            label = HAZARD_INVENTORY_CATEGORY_LABELS[category]
            count = counts.get(category, 0)
            item = QListWidgetItem(f"{label} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.category_list.addItem(item)
        index = HAZARD_INVENTORY_CATEGORIES.index(selected_category)
        self.category_list.setCurrentRow(index)
        self.category_list.blockSignals(False)

    def _load_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._identification_id is None:
            self.table.blockSignals(False)
            return

        relation_counts = hazard_inventory_relation_service.count_active_by_source_items(
            self._identification_id
        )
        event_counts = hazard_event_service.count_active_by_inventory_items(
            self._identification_id
        )
        items = hazard_inventory_item_service.get_by_category(
            self._identification_id,
            self._current_category,
            include_inactive=True,
        )
        self.table.setRowCount(len(items))
        selected_row = -1
        for row, item in enumerate(items):
            self.table.setItem(row, INVENTORY_COL_ID, QTableWidgetItem(str(item.id)))
            display_name = format_inventory_item_display_name(
                item.name,
                relation_count=relation_counts.get(item.id, 0),
                event_count=event_counts.get(item.id, 0),
            )
            self.table.setItem(row, INVENTORY_COL_NAME, QTableWidgetItem(display_name))
            self.table.setItem(
                row,
                INVENTORY_COL_DESCRIPTION,
                create_preview_table_item(item.description),
            )
            self.table.setItem(
                row,
                INVENTORY_COL_ACTIVE,
                QTableWidgetItem("Ano" if item.active else "Ne"),
            )
            if self._selected_item_id == item.id:
                selected_row = row

        configure_table_columns(self.table, "hazard_inventory_items")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)

    def _on_category_changed(self, row: int) -> None:
        item = self.category_list.item(row)
        if item is None:
            return
        category = item.data(Qt.ItemDataRole.UserRole)
        if category:
            self._current_category = category
            self._selected_item_id = None
            self._load_table()
            self._sync_analysis_selection()

    def _on_item_selection_changed(self) -> None:
        item = self._selected_item()
        self._selected_item_id = item.id if item is not None else None
        self._sync_analysis_selection()

    def _sync_analysis_selection(self) -> None:
        item = self._selected_item()
        self.analysis_widget.set_source_item(
            item,
            identification_id=self._identification_id,
            read_only=self._read_only,
        )

    def _selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), INVENTORY_COL_ID)
        if id_item is None:
            return None
        return hazard_inventory_item_service.get_by_id(int(id_item.text()))

    def refresh_analysis_and_counts(self) -> None:
        self._load_table()
        self.analysis_widget.refresh()
