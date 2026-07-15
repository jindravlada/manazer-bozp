"""Vyhledávací výběr ohrožené skupiny s možností vytvoření nové položky číselníku."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter, QMessageBox

from core.utils.czech_sort import czech_sorted
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.exposed_group_service import (
    ExposedGroupError,
    ExposedGroupMatchKind,
    exposed_group_service,
)

ADD_NEW_EXPOSED_GROUP = object()


def add_new_exposed_group_label(name: str) -> str:
    return f'Přidat novou skupinu „{name}"'


class ExposedGroupSelector(SearchComboBox):
    """Vyhledávací výběr aktivních ohrožených skupin s vytvořením nové položky."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=False)
        self._groups_by_id: dict[int, object] = {}
        self._preserve_group_id: int | None = None
        self._add_new_name = ""
        self._handling_create = False

        self.lineEdit().returnPressed.connect(self._on_return_pressed)
        self.activated.connect(self._on_activated)
        self.reload()

    def reload(self, preserve_id: int | None = None) -> None:
        if preserve_id is not None:
            self._preserve_group_id = preserve_id

        current_id = self._resolve_current_group_id()
        preserve_id = self._preserve_group_id or current_id
        self._preserve_group_id = None

        self.blockSignals(True)
        self.clear()
        self._groups_by_id = {}
        self._add_new_name = ""

        groups = czech_sorted(
            exposed_group_service.get_active_all(),
            key=lambda group: group.name.casefold(),
        )
        for group in groups:
            self._append_group_item(group)

        if preserve_id is not None and preserve_id not in self._groups_by_id:
            group = exposed_group_service.get_by_id(preserve_id)
            if group is not None:
                label = group.name
                if not group.active:
                    label = f"{label} (neaktivní)"
                self._groups_by_id[group.id] = group
                self.addItem(label, group.id)

        self._update_completer()
        if preserve_id is not None:
            self.set_group_id(preserve_id)
        elif self.count() > 0:
            self.setCurrentIndex(-1)
            self.setCurrentText("")

        self.blockSignals(False)

    def showPopup(self) -> None:
        selected_id = self._resolve_current_group_id()
        self._rebuild_popup_items(selected_id=selected_id)
        super().showPopup()

    def current_group_id(self) -> int | None:
        return self._resolve_current_group_id()

    def set_group_id(self, group_id: int | None) -> None:
        if group_id is None:
            self.setCurrentIndex(-1)
            self.setCurrentText("")
            return

        index = self.findData(group_id)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        group = exposed_group_service.get_by_id(group_id)
        if group is not None:
            label = group.name
            if not group.active:
                label = f"{label} (neaktivní)"
            self._groups_by_id[group.id] = group
            self.addItem(label, group.id)
            self.setCurrentIndex(self.count() - 1)
            self._update_completer()
            return

        self.setCurrentIndex(-1)
        self.setCurrentText("")

    def ensure_selected_group_id(self, parent=None) -> int | None:
        group_id = self.current_group_id()
        if group_id is not None:
            return group_id

        text = self.currentText().strip()
        if not text:
            return None

        resolved = self._resolve_name_to_group_id(text, parent=parent or self.window())
        if resolved is None:
            return None

        self.reload(preserve_id=resolved)
        self.set_group_id(resolved)
        return resolved

    def _resolve_current_group_id(self) -> int | None:
        data = self.currentData()
        if isinstance(data, int):
            return data

        text = self.currentText().strip()
        if not text:
            return None

        match = exposed_group_service.classify_name(text)
        if match.kind == ExposedGroupMatchKind.ACTIVE and len(match.groups) == 1:
            return match.groups[0].id
        return None

    def _append_group_item(self, group) -> None:
        self._groups_by_id[group.id] = group
        self.addItem(group.name, group.id)

    def _update_completer(self) -> None:
        names = [self.itemText(index) for index in range(self.count())]
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

    def _rebuild_popup_items(self, *, selected_id: int | None) -> None:
        text = self.currentText().strip()
        self.blockSignals(True)
        self.clear()
        self._groups_by_id = {}
        self._add_new_name = ""

        groups = czech_sorted(
            exposed_group_service.get_active_all(),
            key=lambda group: group.name.casefold(),
        )
        needle = text.casefold()
        filtered = [
            group
            for group in groups
            if not needle or needle in group.name.casefold()
        ]
        for group in filtered:
            self._append_group_item(group)

        if selected_id is not None:
            group = exposed_group_service.get_by_id(selected_id)
            if group is not None and group.id not in self._groups_by_id:
                label = group.name
                if not group.active:
                    label = f"{label} (neaktivní)"
                self._groups_by_id[group.id] = group
                self.addItem(label, group.id)

        if text and self._exact_active_match(text) is None:
            self._add_new_name = text
            self.addItem(add_new_exposed_group_label(text), ADD_NEW_EXPOSED_GROUP)

        if selected_id is not None:
            index = self.findData(selected_id)
            if index >= 0:
                self.setCurrentIndex(index)
        elif text:
            self.setCurrentText(text)

        self.blockSignals(False)

    def _exact_active_match(self, text: str):
        match = exposed_group_service.classify_name(text)
        if match.kind == ExposedGroupMatchKind.ACTIVE and len(match.groups) == 1:
            return match.groups[0]
        return None

    def _on_activated(self, index: int) -> None:
        if self._handling_create:
            return
        data = self.itemData(index)
        if data is not ADD_NEW_EXPOSED_GROUP:
            return

        name = self._add_new_name or self.currentText().strip()
        self._handling_create = True
        try:
            group_id = self._resolve_name_to_group_id(name)
            if group_id is not None:
                self.reload(preserve_id=group_id)
                self.set_group_id(group_id)
        finally:
            self._handling_create = False

    def _on_return_pressed(self) -> None:
        if self._handling_create:
            return

        group_id = self.current_group_id()
        if group_id is not None:
            return

        text = self.currentText().strip()
        if not text:
            return

        match = self._exact_active_match(text)
        if match is not None:
            self.set_group_id(match.id)
            return

        self._handling_create = True
        try:
            resolved = self._resolve_name_to_group_id(text)
            if resolved is not None:
                self.reload(preserve_id=resolved)
                self.set_group_id(resolved)
        finally:
            self._handling_create = False

    def _resolve_name_to_group_id(
        self,
        name: str,
        *,
        parent=None,
    ) -> int | None:
        normalized = " ".join((name or "").split()).strip()
        if not normalized:
            return None

        dialog_parent = parent or self.window()
        match = exposed_group_service.classify_name(normalized)

        if match.kind == ExposedGroupMatchKind.ACTIVE:
            return match.groups[0].id

        if match.kind == ExposedGroupMatchKind.INACTIVE:
            group = match.groups[0]
            reply = QMessageBox.question(
                dialog_parent,
                "Ohrožená skupina",
                (
                    f"V číselníku existuje neaktivní skupina „{group.name}“.\n\n"
                    "Aktivovat a použít?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return None
            try:
                exposed_group_service.activate(group.id)
            except ExposedGroupError as error:
                QMessageBox.warning(dialog_parent, "Ohrožená skupina", str(error))
                return None
            return group.id

        if match.kind == ExposedGroupMatchKind.AMBIGUOUS:
            names = ", ".join(group.name for group in match.groups)
            QMessageBox.warning(
                dialog_parent,
                "Ohrožená skupina",
                f"Název odpovídá více položkám číselníku: {names}.",
            )
            return None

        reply = QMessageBox.question(
            dialog_parent,
            "Ohrožená skupina",
            f'Vytvořit novou skupinu „{normalized}" a použít ji?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return None
        try:
            group = exposed_group_service.create_group(name=normalized)
        except ExposedGroupError as error:
            QMessageBox.warning(dialog_parent, "Ohrožená skupina", str(error))
            return None
        return group.id
