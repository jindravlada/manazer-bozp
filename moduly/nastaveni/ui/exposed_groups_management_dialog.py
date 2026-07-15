from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.nastaveni.sluzby.exposed_group_service import (
    ExposedGroupError,
    exposed_group_service,
)
from moduly.nastaveni.ui.exposed_group_dialog import ExposedGroupDialog


class ExposedGroupsManagementDialog(QDialog):
    """Správa číselníku ohrožených skupin – lze otevřít z dialogu posouzení."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ohrožené skupiny osob")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Společný číselník ohrožených skupin osob pro posouzení rizik a další moduly.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_group)
        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_group)
        self.toggle_button = QPushButton("Deaktivovat / Aktivovat")
        self.toggle_button.clicked.connect(self.toggle_selected_group_active)
        self.filter = QComboBox()
        self.filter.addItems(["Aktivní", "Všechny"])
        self.filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.filter)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Název", "Poznámka", "Aktivní"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected_group)
        configure_table_columns(self.table, "exposed_groups")
        self.text_filter = FilterBar(self.table)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        close_button = QPushButton("Zavřít")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.refresh()

    def refresh(self) -> None:
        include_inactive = self.filter.currentIndex() == 1
        groups = exposed_group_service.get_all(include_inactive=include_inactive)
        self.table.setRowCount(len(groups))
        for row_index, group in enumerate(groups):
            self.table.setItem(row_index, 0, QTableWidgetItem(group.name))
            self.table.setItem(row_index, 1, QTableWidgetItem(group.note or ""))
            self.table.setItem(
                row_index,
                2,
                QTableWidgetItem("Ano" if group.active else "Ne"),
            )
            self.table.item(row_index, 0).setData(0, group.id)

    def _selected_group_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return item.data(0) if item is not None else None

    def add_group(self) -> None:
        dialog = ExposedGroupDialog(self)
        if not dialog.exec():
            return
        try:
            data = dialog.get_data()
            exposed_group_service.create_group(**data)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny osob", str(error))
            return
        self.refresh()

    def edit_selected_group(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            QMessageBox.information(self, "Ohrožené skupiny osob", "Vyberte skupinu.")
            return
        group = exposed_group_service.get_by_id(group_id)
        if group is None:
            return
        dialog = ExposedGroupDialog(self, group=group)
        if not dialog.exec():
            return
        try:
            data = dialog.get_data()
            exposed_group_service.update_group(group_id, **data)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny osob", str(error))
            return
        self.refresh()

    def toggle_selected_group_active(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            QMessageBox.information(self, "Ohrožené skupiny osob", "Vyberte skupinu.")
            return
        group = exposed_group_service.get_by_id(group_id)
        if group is None:
            return
        try:
            if group.active:
                exposed_group_service.deactivate(group_id)
            else:
                exposed_group_service.activate(group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny osob", str(error))
            return
        self.refresh()
