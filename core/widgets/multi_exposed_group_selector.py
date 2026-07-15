"""Multivýběr ohrožených skupin se stejným vyhledávacím selectorem jako dosud."""

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

from core.widgets.exposed_group_selector import ExposedGroupSelector
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service


class MultiExposedGroupSelector(QWidget):
    """Výběr více ohrožených skupin: vyhledávací selector + seznam + Přidat/Odebrat."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = ExposedGroupSelector(self)
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
        self.selector.lineEdit().returnPressed.connect(self.add_current)

    def add_current(self) -> None:
        group_id = self.selector.ensure_selected_group_id(self.window())
        if group_id is None:
            return
        if group_id in self.selected_group_ids():
            self.selector.set_group_id(None)
            return
        group = exposed_group_service.get_by_id(group_id)
        label = group.name if group is not None else f"#{group_id}"
        if group is not None and not group.active:
            label = f"{label} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, group_id)
        self.list_widget.addItem(item)
        self.selector.set_group_id(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_group_ids(self) -> list[int]:
        ids: list[int] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw is not None:
                ids.append(int(raw))
        return ids

    def set_group_ids(self, group_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for group_id in group_ids or ():
            group = exposed_group_service.get_by_id(group_id)
            if group is None:
                continue
            label = group.name
            if not group.active:
                label = f"{label} (neaktivní)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            self.list_widget.addItem(item)

    def reload(self, preserve_ids: list[int] | None = None) -> None:
        current = preserve_ids if preserve_ids is not None else self.selected_group_ids()
        self.selector.reload()
        self.set_group_ids(current)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.selector.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)
