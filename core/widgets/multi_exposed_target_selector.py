"""Multivýběr ohrožených skupin z funkcí/rolí i číselníku rizik (RISK-UX-6)."""

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

from core.widgets.exposed_target_selector import ExposedTargetSelector
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    ExposedTargetRef,
    resolve_exposed_target_display_name,
)


class MultiExposedTargetSelector(QWidget):
    """Výběr více položek: společný vyhledávací seznam + Přidat/Odebrat."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = ExposedTargetSelector(self)
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
        ref = self.selector.ensure_selected_ref()
        if ref is None:
            return
        self._append_ref(ref)
        self.selector.set_ref(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_refs(self) -> list[ExposedTargetRef]:
        self._commit_pending_selector_ref()
        return self._list_refs()

    def selected_group_ids(self) -> list[int]:
        """Zpětná kompatibilita – pouze hazard_group."""
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import SOURCE_TYPE_HAZARD_GROUP

        return [
            ref.source_id
            for ref in self.selected_refs()
            if ref.source_type == SOURCE_TYPE_HAZARD_GROUP
        ]

    def set_refs(self, refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None) -> None:
        self.list_widget.clear()
        for ref in refs or ():
            self._append_ref(ref)

    def set_group_ids(self, group_ids: list[int] | tuple[int, ...] | None) -> None:
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import refs_from_legacy_group_ids

        self.set_refs(refs_from_legacy_group_ids(group_ids))

    def reload(self, preserve_refs: list[ExposedTargetRef] | None = None) -> None:
        current = preserve_refs if preserve_refs is not None else self.selected_refs()
        self.selector.reload()
        self.set_refs(current)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.selector.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)

    def _on_selector_activated(self, _index: int) -> None:
        ref = self.selector.current_ref()
        if ref is None:
            return
        self._append_ref(ref)
        self.selector.set_ref(None)

    def _commit_pending_selector_ref(self) -> None:
        ref = self.selector.current_ref()
        if ref is None:
            return
        self._append_ref(ref)
        self.selector.set_ref(None)

    def _list_refs(self) -> list[ExposedTargetRef]:
        refs: list[ExposedTargetRef] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(raw, tuple) or len(raw) != 2:
                continue
            try:
                refs.append(ExposedTargetRef(str(raw[0]), int(raw[1])))
            except (TypeError, ValueError):
                continue
        return refs

    def _append_ref(self, ref: ExposedTargetRef) -> None:
        if any(existing.key == ref.key for existing in self._list_refs()):
            return
        label = resolve_exposed_target_display_name(ref)
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, (ref.source_type, ref.source_id))
        self.list_widget.addItem(item)
