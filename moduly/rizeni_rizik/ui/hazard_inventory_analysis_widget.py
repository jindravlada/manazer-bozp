from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORY_LABELS,
    INVENTORY_ANALYSIS_TITLE,
    INVENTORY_RELATION_DIALOG_TITLE,
    RELATION_COL_ACTIVE,
    RELATION_COL_CATEGORY,
    RELATION_COL_ID,
    RELATION_COL_NAME,
    RELATION_COL_NOTE,
    RELATION_COL_TYPE,
    RELATION_COLUMN_COUNT,
    RELATION_TABLE_HEADERS,
    WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
    WORKPLACE_ANALYSIS_SELECT_ITEM,
    format_inventory_item_display_name,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import (
    HazardInventoryRelationError,
    hazard_inventory_relation_service,
)
from moduly.rizeni_rizik.sluzby.identified_hazard_service import identified_hazard_service
from moduly.rizeni_rizik.ui.hazard_inventory_relation_dialog import HazardInventoryRelationDialog


class HazardInventoryAnalysisWidget(QWidget):
    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)

        self._on_changed = on_changed

        self._identification_id: int | None = None
        self._source_item = None
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox(INVENTORY_ANALYSIS_TITLE)
        group_layout = QVBoxLayout(group)

        self.header_label = QLabel(WORKPLACE_ANALYSIS_SELECT_ITEM)
        self.header_label.setWordWrap(True)
        group_layout.addWidget(self.header_label)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        group_layout.addWidget(self.detail_label)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat souvislost")
        self.edit_btn = QPushButton("Upravit souvislost")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        group_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(RELATION_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(RELATION_TABLE_HEADERS)
        self.table.setColumnHidden(RELATION_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_inventory_relations")
        group_layout.addWidget(self.table)

        layout.addWidget(group)

        self.add_btn.clicked.connect(self.add_relation)
        self.edit_btn.clicked.connect(self.edit_selected_relation)
        self.activate_btn.clicked.connect(self.activate_selected_relation)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_relation)
        self.table.doubleClicked.connect(self.edit_selected_relation)

        self.set_source_item(None, identification_id=None, read_only=False)

    def set_source_item(
        self,
        source_item,
        *,
        identification_id: int | None,
        read_only: bool,
    ) -> None:
        self._source_item = source_item
        self._identification_id = identification_id
        self._read_only = read_only
        editable = (
            not read_only
            and identification_id is not None
            and source_item is not None
        )
        for button in (self.add_btn, self.edit_btn, self.activate_btn, self.deactivate_btn):
            button.setEnabled(editable)
        self.refresh()

    def refresh(self) -> None:
        if self._source_item is None:
            self.header_label.setText(WORKPLACE_ANALYSIS_SELECT_ITEM)
            self.detail_label.setText("")
            self.table.setRowCount(0)
            return

        category_label = HAZARD_INVENTORY_CATEGORY_LABELS.get(
            self._source_item.category,
            self._source_item.category,
        )
        relation_count = hazard_inventory_relation_service.count_active_for_source(
            self._source_item.id
        )
        hazard_count = identified_hazard_service.count_active_for_inventory_item(
            self._source_item.id
        )
        self.header_label.setText(
            format_inventory_item_display_name(
                self._source_item.name,
                relation_count=relation_count,
                hazard_count=hazard_count,
            )
        )
        description = self._source_item.description.strip() or "—"
        self.detail_label.setText(f"Kategorie: {category_label}\nPopis: {description}")
        self._load_relations()

    def add_relation(self) -> None:
        if not self._ensure_editable():
            return

        dialog = HazardInventoryRelationDialog(
            self,
            hazard_identification_id=self._identification_id,
            source_item=self._source_item,
        )
        if dialog.exec():
            self._notify_changed()

    def edit_selected_relation(self) -> None:
        relation = self._selected_relation()
        if relation is None:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Vyberte souvislost.",
            )
            return

        dialog = HazardInventoryRelationDialog(
            self,
            hazard_identification_id=self._identification_id,
            source_item=self._source_item,
            relation=relation,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_changed()

    def activate_selected_relation(self) -> None:
        if not self._ensure_editable():
            return

        relation = self._selected_relation()
        if relation is None:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Vyberte souvislost.",
            )
            return
        if relation.active:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Souvislost je již aktivní.",
            )
            return

        try:
            hazard_inventory_relation_service.activate_relation(relation.id)
        except HazardInventoryRelationError as error:
            QMessageBox.warning(self, INVENTORY_RELATION_DIALOG_TITLE, str(error))
            return
        self._notify_changed()

    def deactivate_selected_relation(self) -> None:
        if not self._ensure_editable():
            return

        relation = self._selected_relation()
        if relation is None:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Vyberte souvislost.",
            )
            return
        if not relation.active:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Souvislost je již neaktivní.",
            )
            return

        hazard_inventory_relation_service.deactivate_relation(relation.id)
        self._notify_changed()

    def _notify_changed(self) -> None:
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()

    def _ensure_editable(self) -> bool:
        if self._read_only:
            QMessageBox.information(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                WORKPLACE_ANALYSIS_READ_ONLY_MESSAGE,
            )
            return False
        return True

    def _load_relations(self) -> None:
        rows = hazard_inventory_relation_service.get_for_source_item(
            self._source_item.id,
            include_inactive=True,
        )
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            relation = row.relation
            self.table.setItem(row_index, RELATION_COL_ID, QTableWidgetItem(str(relation.id)))
            self.table.setItem(row_index, RELATION_COL_TYPE, QTableWidgetItem(row.relation_type_label))
            self.table.setItem(row_index, RELATION_COL_CATEGORY, QTableWidgetItem(row.target_category_label))
            self.table.setItem(row_index, RELATION_COL_NAME, QTableWidgetItem(row.target_name))
            self.table.setItem(
                row_index,
                RELATION_COL_NOTE,
                create_preview_table_item(relation.note),
            )
            self.table.setItem(
                row_index,
                RELATION_COL_ACTIVE,
                QTableWidgetItem("Ano" if relation.active else "Ne"),
            )
        configure_table_columns(self.table, "hazard_inventory_relations")

    def _selected_relation(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), RELATION_COL_ID)
        if id_item is None:
            return None
        return hazard_inventory_relation_service.get_by_id(int(id_item.text()))
