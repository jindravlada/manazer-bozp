from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_text,
)
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
        self.edit_button = QPushButton("Upravit")
        self.edit_button.clicked.connect(self.edit_selected_group)
        self.edit_button.setEnabled(False)
        self.activate_button = QPushButton("Aktivovat")
        self.activate_button.clicked.connect(self.activate_selected_group)
        self.activate_button.setEnabled(False)
        self.deactivate_button = QPushButton("Deaktivovat")
        self.deactivate_button.clicked.connect(self.deactivate_selected_group)
        self.deactivate_button.setEnabled(False)
        self.filter = QComboBox()
        self.filter.addItems(["Aktivní", "Všechny"])
        self.filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.activate_button)
        toolbar.addWidget(self.deactivate_button)
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
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        configure_table_columns(self.table, "exposed_groups")
        enable_typed_sorting(self.table)
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
        with sorting_paused(self.table):
            self.table.setRowCount(len(groups))
            for row_index, group in enumerate(groups):
                name_item = create_typed_item(group.name, typed_text(group.name), stable_id=group.id)
                name_item.setData(Qt.ItemDataRole.UserRole, group.id)
                self.table.setItem(row_index, 0, name_item)
                self.table.setItem(
                    row_index, 1, create_typed_item(group.note or "", typed_text(group.note), stable_id=group.id)
                )
                self.table.setItem(
                    row_index,
                    2,
                    create_typed_item(
                        "Ano" if group.active else "Ne", typed_bool(group.active), stable_id=group.id
                    ),
                )
        configure_table_columns(self.table, "exposed_groups")
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        group_id = self._selected_group_id()
        group = exposed_group_service.get_by_id(group_id) if group_id is not None else None
        single = group is not None
        self.edit_button.setEnabled(single)
        self.activate_button.setEnabled(single and not group.active)
        self.deactivate_button.setEnabled(single and group.active)

    def _selected_group_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

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

    def activate_selected_group(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            return
        try:
            exposed_group_service.activate(group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny osob", str(error))
            return
        self.refresh()

    def deactivate_selected_group(self) -> None:
        group_id = self._selected_group_id()
        if group_id is None:
            return
        try:
            exposed_group_service.deactivate(group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny osob", str(error))
            return
        self.refresh()
