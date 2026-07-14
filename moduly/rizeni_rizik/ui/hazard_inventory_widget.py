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
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import hazard_inventory_item_service
from moduly.rizeni_rizik.ui.hazard_inventory_item_dialog import HazardInventoryItemDialog


class HazardInventoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None
        self._read_only = False
        self._current_category = HAZARD_INVENTORY_CATEGORIES[0]

        layout = QVBoxLayout(self)

        intro = QLabel(INVENTORY_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.toolbar.addWidget(self.add_btn)
        self.toolbar.addWidget(self.edit_btn)
        self.toolbar.addWidget(self.activate_btn)
        self.toolbar.addWidget(self.deactivate_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setMinimumWidth(240)
        splitter.addWidget(self.category_list)

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget()
        self.table.setColumnCount(INVENTORY_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(INVENTORY_TABLE_HEADERS)
        self.table.setColumnHidden(INVENTORY_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_inventory_items")
        table_layout.addWidget(self.table)
        splitter.addWidget(table_host)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        self.add_btn.clicked.connect(self.add_item)
        self.edit_btn.clicked.connect(self.edit_selected_item)
        self.activate_btn.clicked.connect(self.activate_selected_item)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_item)
        self.category_list.currentRowChanged.connect(self._on_category_changed)
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
        self._set_actions_enabled(not read_only and identification_id is not None)
        self.refresh()

    def refresh(self) -> None:
        self._populate_categories()
        self._load_table()

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
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Vyberte položku inventury.")
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
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Vyberte položku inventury.")
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
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Vyberte položku inventury.")
            return
        if not item.active:
            QMessageBox.information(self, INVENTORY_ITEM_DIALOG_TITLE, "Položka je již neaktivní.")
            return

        hazard_inventory_item_service.deactivate_item(item.id)
        self.refresh()

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
                "Inventura je u dokončené nebo archivované identifikace pouze pro čtení.",
            )
            return False
        return True

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (self.add_btn, self.edit_btn, self.activate_btn, self.deactivate_btn):
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
        self.table.setRowCount(0)
        if self._identification_id is None:
            return

        items = hazard_inventory_item_service.get_by_category(
            self._identification_id,
            self._current_category,
            include_inactive=True,
        )
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, INVENTORY_COL_ID, QTableWidgetItem(str(item.id)))
            self.table.setItem(row, INVENTORY_COL_NAME, QTableWidgetItem(item.name))
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
        configure_table_columns(self.table, "hazard_inventory_items")

    def _on_category_changed(self, row: int) -> None:
        item = self.category_list.item(row)
        if item is None:
            return
        category = item.data(Qt.ItemDataRole.UserRole)
        if category:
            self._current_category = category
            self._load_table()

    def _selected_item(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), INVENTORY_COL_ID)
        if id_item is None:
            return None
        return hazard_inventory_item_service.get_by_id(int(id_item.text()))
