"""Správa číselníku Funkce / role používaného v Řízení rizik."""

from __future__ import annotations

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
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.nastaveni.ui.responsibility_role_dialog import ResponsibilityRoleDialog


class ResponsibilityRolesManagementDialog(QDialog):
    """Správa rolí/profesí ze stejného číselníku jako katalog rizik."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Funkce / role")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Číselník funkcí a rolí používaný v katalogu zdrojů rizik "
            "a při posuzování rizik. Stejný seznam je dostupný také "
            "v Nastavení → Funkce / role."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_role)
        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_role)
        self.activate_button = QPushButton("Aktivovat")
        self.activate_button.clicked.connect(self.activate_selected_role)
        self.deactivate_button = QPushButton("Deaktivovat")
        self.deactivate_button.clicked.connect(self.deactivate_selected_role)
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
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Název", "Popis", "Aktivní"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected_role)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        configure_table_columns(self.table, "responsibility_roles")
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
        roles = responsibility_role_service.get_all(include_inactive=include_inactive)
        with sorting_paused(self.table):
            self.table.setRowCount(len(roles))
            for row_index, role in enumerate(roles):
                name_item = create_typed_item(
                    role.name,
                    typed_text(role.name),
                    stable_id=role.id,
                )
                name_item.setData(Qt.ItemDataRole.UserRole, role.id)
                self.table.setItem(row_index, 0, name_item)
                self.table.setItem(
                    row_index,
                    1,
                    create_typed_item(
                        role.description or "",
                        typed_text(role.description or ""),
                        stable_id=role.id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    2,
                    create_typed_item(
                        "Ano" if role.active else "Ne",
                        typed_bool(bool(role.active)),
                        stable_id=role.id,
                    ),
                )
        configure_table_columns(self.table, "responsibility_roles")
        self.text_filter.update_count()
        self._update_action_buttons()

    def _selected_role_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        raw = item.data(Qt.ItemDataRole.UserRole)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _update_action_buttons(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        self.activate_button.setEnabled(not role.active)
        self.deactivate_button.setEnabled(role.active)

    def add_role(self) -> None:
        dialog = ResponsibilityRoleDialog(self)
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            responsibility_role_service.create_role(**data)
        except ValueError as error:
            QMessageBox.warning(self, "Funkce / role", str(error))
            return
        self.refresh()

    def edit_selected_role(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None:
            QMessageBox.information(self, "Funkce / role", "Vyberte roli.")
            return
        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            QMessageBox.warning(self, "Funkce / role", "Role nebyla nalezena.")
            self.refresh()
            return
        dialog = ResponsibilityRoleDialog(self, role=role)
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            responsibility_role_service.update_role(role_id, **data)
        except ValueError as error:
            QMessageBox.warning(self, "Funkce / role", str(error))
            return
        self.refresh()

    def activate_selected_role(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None:
            return
        responsibility_role_service.activate(role_id)
        self.refresh()

    def deactivate_selected_role(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None:
            return
        responsibility_role_service.deactivate(role_id)
        self.refresh()
