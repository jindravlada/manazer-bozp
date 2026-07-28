"""Multivýběr funkcí/rolí: našeptávač + Přidat/Odebrat (stejný UX jako MultiExposedGroupSelector)."""

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

from core.widgets.search_responsibility_role_selector import (
    SearchResponsibilityRoleSelector,
)
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)


class MultiResponsibilityRoleSelector(QWidget):
    """Výběr více rolí/profesí: vyhledávací selector + seznam + Přidat/Odebrat."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = SearchResponsibilityRoleSelector(self)
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
        role_id = self.selector.ensure_selected_role_id()
        if role_id is None:
            return
        self._append_role_id(role_id)
        self.selector.set_role_id(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_role_ids(self) -> list[int]:
        self._commit_pending_selector_role()
        return self._list_role_ids()

    def set_role_ids(self, role_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for role_id in role_ids or ():
            self._append_role_id(int(role_id))

    def reload(self, preserve_ids: list[int] | None = None) -> None:
        current = preserve_ids if preserve_ids is not None else self.selected_role_ids()
        self.selector.reload()
        self.set_role_ids(current)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.selector.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)

    def available_role_ids(self) -> list[int]:
        """ID aktivních rolí v našeptávači (pro testy / kontrolu nabídky)."""
        return [
            int(self.selector.itemData(index))
            for index in range(self.selector.count())
            if self.selector.itemData(index) is not None
        ]

    def _on_selector_activated(self, _index: int) -> None:
        role_id = self.selector.current_role_id()
        if role_id is None:
            return
        self._append_role_id(role_id)
        self.selector.set_role_id(None)

    def _commit_pending_selector_role(self) -> None:
        role_id = self.selector.current_role_id()
        if role_id is None:
            return
        self._append_role_id(role_id)
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
        label = role.name if role is not None else f"#{role_id}"
        if role is not None and not role.active:
            label = f"{label} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, int(role_id))
        self.list_widget.addItem(item)
