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
        self.selector.activated.connect(self._on_selector_activated)

    def add_current(self) -> None:
        group_id = self.selector.ensure_selected_group_id(self.window())
        if group_id is None:
            return
        self._append_group_id(group_id)
        self.selector.set_group_id(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_group_ids(self) -> list[int]:
        """Vrátí ID skupin ze seznamu včetně dosud nepřidaného výběru v selectoru."""
        self._commit_pending_selector_group()
        return self._list_group_ids()

    def set_group_ids(self, group_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for group_id in group_ids or ():
            self._append_group_id(int(group_id))

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

    def _on_selector_activated(self, _index: int) -> None:
        group_id = self.selector.current_group_id()
        if group_id is None:
            return
        self._append_group_id(group_id)
        self.selector.set_group_id(None)

    def _commit_pending_selector_group(self) -> None:
        """Při čtení hodnot zahrne i výběr v comboboxu, který ještě nebyl Přidán."""
        group_id = self.selector.current_group_id()
        if group_id is None:
            return
        self._append_group_id(group_id)
        self.selector.set_group_id(None)

    def _list_group_ids(self) -> list[int]:
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

    def _append_group_id(self, group_id: int) -> None:
        if group_id in self._list_group_ids():
            return
        group = exposed_group_service.get_by_id(group_id)
        label = group.name if group is not None else f"#{group_id}"
        if group is not None and not group.active:
            label = f"{label} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, int(group_id))
        self.list_widget.addItem(item)
