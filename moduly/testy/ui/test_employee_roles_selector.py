"""Výběr jedné nebo více funkcí / rolí z číselníku."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.responsibility_role_selector import ResponsibilityRoleSelector
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)


class TestEmployeeRolesSelector(QWidget):
    """Aktivní funkce z číselníku; již přiřazená neaktivní role zůstane v seznamu."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = ResponsibilityRoleSelector(self, include_empty=True)
        self.btn_add = QPushButton("Přidat")
        self.btn_remove = QPushButton("Odebrat")
        top.addWidget(self.selector, 1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_remove)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(72)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        layout.addLayout(top)
        layout.addWidget(self.list_widget)

        self.btn_add.clicked.connect(self.add_current)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.selector.activated.connect(self._on_selector_activated)

    def add_current(self) -> None:
        role_id = self.selector.current_role_id()
        if role_id is None:
            return
        self._append_role_id(int(role_id))
        self.selector.set_role_id(None)

    def remove_selected(self) -> None:
        for item in list(self.list_widget.selectedItems()):
            self.list_widget.takeItem(self.list_widget.row(item))

    def selected_role_ids(self) -> list[int]:
        self._commit_pending_selector_role()
        return self._list_role_ids()

    def set_role_ids(self, role_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for role_id in role_ids or ():
            self._append_role_id(int(role_id))

    def _on_selector_activated(self, _index: int) -> None:
        role_id = self.selector.current_role_id()
        if role_id is None:
            return
        self._append_role_id(int(role_id))
        self.selector.set_role_id(None)

    def _commit_pending_selector_role(self) -> None:
        role_id = self.selector.current_role_id()
        if role_id is None:
            return
        self._append_role_id(int(role_id))
        self.selector.set_role_id(None)

    def _list_role_ids(self) -> list[int]:
        ids: list[int] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw is None:
                continue
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        return ids

    def _append_role_id(self, role_id: int) -> None:
        if role_id in self._list_role_ids():
            return
        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            label = f"Funkce #{role_id}"
        elif role.active:
            label = role.name
        else:
            label = f"{role.name} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, int(role_id))
        self.list_widget.addItem(item)
