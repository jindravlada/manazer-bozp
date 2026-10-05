"""Vyhledávací výběr funkce/role s našeptávačem (stejný UX jako ExposedGroupSelector)."""

from __future__ import annotations

from collections.abc import Collection

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)


class SearchResponsibilityRoleSelector(SearchComboBox):
    """Vyhledávací výběr aktivních rolí/profesí z číselníku responsibility_roles."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=False)
        self._roles_by_id: dict[int, object] = {}
        self._preserve_role_id: int | None = None
        self.reload()

    def reload(
        self,
        preserve_id: int | None = None,
        *,
        exclude_ids: Collection[int] | None = None,
    ) -> None:
        if preserve_id is not None:
            self._preserve_role_id = preserve_id

        current_id = self.current_role_id()
        preserve_id = self._preserve_role_id or current_id
        self._preserve_role_id = None
        excluded = {int(role_id) for role_id in exclude_ids or ()}

        line_edit = self.lineEdit()
        self.blockSignals(True)
        if line_edit is not None:
            line_edit.blockSignals(True)
        self.clear()
        self._roles_by_id = {}

        roles = czech_sorted(
            responsibility_role_service.get_all(include_inactive=False),
            key=lambda role: role.name.casefold(),
        )
        for role in roles:
            role_id = int(role.id)
            if role_id in excluded:
                continue
            self._roles_by_id[role_id] = role
            self.addItem(role.name, role_id)

        if (
            preserve_id is not None
            and preserve_id not in excluded
            and preserve_id not in self._roles_by_id
        ):
            role = responsibility_role_service.get_by_id(preserve_id)
            if role is not None:
                label = role.name
                if not role.active:
                    label = f"{label} (neaktivní)"
                self._roles_by_id[int(role.id)] = role
                self.addItem(label, int(role.id))

        self._update_completer()
        if preserve_id is not None and preserve_id not in excluded:
            self.set_role_id(preserve_id)
        else:
            self.setCurrentIndex(-1)
            self.setCurrentText("")
        self.blockSignals(False)
        if line_edit is not None:
            line_edit.blockSignals(False)

    def current_role_id(self) -> int | None:
        index = self.currentIndex()
        text = self.currentText().strip()
        if index < 0 or self.itemText(index).strip().casefold() != text.casefold():
            return None
        data = self.itemData(index)
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def set_role_id(self, role_id: int | None) -> None:
        if role_id is None:
            self.setCurrentIndex(-1)
            self.setCurrentText("")
            return
        index = self.findData(int(role_id))
        if index >= 0:
            self.setCurrentIndex(index)
            return
        role = responsibility_role_service.get_by_id(int(role_id))
        label = role.name if role is not None else f"#{role_id}"
        if role is not None and not role.active:
            label = f"{label} (neaktivní)"
        self.addItem(label, int(role_id))
        self.setCurrentIndex(self.count() - 1)
        self._update_completer()

    def ensure_selected_role_id(self) -> int | None:
        role_id = self.current_role_id()
        if role_id is not None:
            return role_id
        text = self.currentText().strip()
        if not text:
            return None
        for index in range(self.count()):
            if self.itemText(index).casefold() == text.casefold():
                data = self.itemData(index)
                if data is None:
                    continue
                try:
                    self.setCurrentIndex(index)
                    return int(data)
                except (TypeError, ValueError):
                    return None
        return None

    def _update_completer(self) -> None:
        names = [self.itemText(index) for index in range(self.count())]
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
