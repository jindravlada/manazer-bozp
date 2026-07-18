from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.filter_bar import FilterBar
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    HazardSourceCategoryError,
    hazard_source_category_service,
)
from moduly.rizeni_rizik.ui.hazard_source_category_dialog import HazardSourceCategoryDialog


class HazardSourceCategoriesManagementDialog(QDialog):
    """Správa číselníku kategorií zdrojů rizik."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kategorie zdrojů rizik")
        self.resize(820, 520)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Číselník kategorií slouží k třídění zdrojů rizik. "
            "Deaktivace kategorie neskrývá existující zdroje ani jejich vazby.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_category)
        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_category)
        self.activate_button = QPushButton("Aktivovat")
        self.activate_button.clicked.connect(self.activate_selected_category)
        self.deactivate_button = QPushButton("Deaktivovat")
        self.deactivate_button.clicked.connect(self.deactivate_selected_category)
        self.filter = QComboBox()
        self.filter.addItems(["Aktivní", "Všechny"])
        self.filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.activate_button)
        toolbar.addWidget(self.deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.filter)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Pořadí", "Název", "Popis", "Aktivní"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected_category)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.text_filter = FilterBar(self.table)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        close_button = QPushButton("Zavřít")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.refresh()

    def refresh(self) -> None:
        include_inactive = self.filter.currentIndex() == 1
        categories = hazard_source_category_service.get_all(
            include_inactive=include_inactive,
        )
        self.table.setRowCount(len(categories))
        for row_index, category in enumerate(categories):
            order_item = QTableWidgetItem(str(category.sort_order))
            order_item.setData(Qt.ItemDataRole.UserRole, category.id)
            self.table.setItem(row_index, 0, order_item)
            self.table.setItem(row_index, 1, QTableWidgetItem(category.name))
            self.table.setItem(row_index, 2, QTableWidgetItem(category.description or ""))
            self.table.setItem(
                row_index,
                3,
                QTableWidgetItem("Ano" if category.active else "Ne"),
            )
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        category = hazard_source_category_service.get_by_id(category_id)
        if category is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        self.activate_button.setEnabled(not category.active)
        self.deactivate_button.setEnabled(category.active)

    def _selected_category_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def add_category(self) -> None:
        dialog = HazardSourceCategoryDialog(self)
        if not dialog.exec():
            return
        try:
            hazard_source_category_service.create_category(**dialog.get_data())
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, "Kategorie zdrojů rizik", str(error))
            return
        self.refresh()

    def edit_selected_category(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            QMessageBox.information(self, "Kategorie zdrojů rizik", "Vyberte kategorii.")
            return
        category = hazard_source_category_service.get_by_id(category_id)
        if category is None:
            return
        dialog = HazardSourceCategoryDialog(self, category=category)
        if not dialog.exec():
            return
        try:
            hazard_source_category_service.update_category(category_id, **dialog.get_data())
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, "Kategorie zdrojů rizik", str(error))
            return
        self.refresh()

    def activate_selected_category(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            return
        try:
            hazard_source_category_service.activate(category_id)
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, "Kategorie zdrojů rizik", str(error))
            return
        self.refresh()

    def deactivate_selected_category(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            return
        try:
            hazard_source_category_service.deactivate(category_id)
        except HazardSourceCategoryError as error:
            QMessageBox.warning(self, "Kategorie zdrojů rizik", str(error))
            return
        self.refresh()
