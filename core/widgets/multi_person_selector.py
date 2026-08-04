"""Multivýběr osob ze stávajícího číselníku PersonSelector."""

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

from core.widgets.person_selector import PersonSelector
from moduly.nastaveni.sluzby.person_service import person_service


class MultiPersonSelector(QWidget):
    """Výběr více osob: PersonSelector + seznam + Přidat / Odebrat."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = PersonSelector(self, include_empty=True, allow_add_new=True)
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
        person_id = self.selector.current_person_id()
        if person_id is None:
            return
        self._append_person_id(person_id)
        self.selector.set_person_id(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def selected_person_ids(self) -> list[int]:
        self._commit_pending_selector()
        return self._list_person_ids()

    def set_person_ids(self, person_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for person_id in person_ids or ():
            self._append_person_id(int(person_id))

    def reload(self, preserve_ids: list[int] | None = None) -> None:
        current = preserve_ids if preserve_ids is not None else self.selected_person_ids()
        self.selector.reload()
        self.set_person_ids(current)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.selector.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)

    def _on_selector_activated(self, _index: int) -> None:
        person_id = self.selector.current_person_id()
        if person_id is None:
            return
        self._append_person_id(person_id)
        self.selector.set_person_id(None)

    def _commit_pending_selector(self) -> None:
        person_id = self.selector.current_person_id()
        if person_id is None:
            return
        self._append_person_id(person_id)
        self.selector.set_person_id(None)

    def _list_person_ids(self) -> list[int]:
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

    def _append_person_id(self, person_id: int) -> None:
        if person_id in self._list_person_ids():
            return
        person = person_service.get_by_id(person_id)
        label = person.display_name if person is not None else f"#{person_id}"
        if person is not None and not person.active:
            label = f"{label} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, int(person_id))
        self.list_widget.addItem(item)
