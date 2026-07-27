"""Vyhledávací výběr ohrožené skupiny z funkcí/rolí i číselníku rizik (RISK-UX-6)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SECTION_LABEL_HAZARD_GROUPS,
    SECTION_LABEL_ROLES,
    SOURCE_TYPE_HAZARD_GROUP,
    SOURCE_TYPE_ROLE,
    ExposedTargetRef,
)


class ExposedTargetSelector(SearchComboBox):
    """Jeden společný seznam: Funkce/role + Ostatní ohrožené skupiny."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=False)
        self._preserve_ref: ExposedTargetRef | None = None
        self.reload()

    def reload(self, preserve_ref: ExposedTargetRef | None = None) -> None:
        if preserve_ref is not None:
            self._preserve_ref = preserve_ref

        current = self.current_ref()
        preserve = self._preserve_ref or current
        self._preserve_ref = None

        self.blockSignals(True)
        self.clear()
        self._rebuild_items(filter_text="", selected_ref=preserve)
        if preserve is not None:
            self.set_ref(preserve)
        else:
            self.setCurrentIndex(-1)
            self.setCurrentText("")
        self.blockSignals(False)

    def showPopup(self) -> None:
        selected = self.current_ref()
        self._rebuild_items(filter_text="", selected_ref=selected)
        if selected is not None:
            self.set_ref(selected)
        super().showPopup()

    def current_ref(self) -> ExposedTargetRef | None:
        data = self.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            try:
                return ExposedTargetRef(str(data[0]), int(data[1]))
            except (TypeError, ValueError):
                return None
        return None

    def set_ref(self, ref: ExposedTargetRef | None) -> None:
        if ref is None:
            self.setCurrentIndex(-1)
            self.setCurrentText("")
            return
        index = self._find_ref_index(ref)
        if index >= 0:
            self.setCurrentIndex(index)
            return
        # Neaktivní / chybějící v seznamu – doplnit ručně.
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
            resolve_exposed_target_display_name,
        )

        label = resolve_exposed_target_display_name(ref)
        self.addItem(label, (ref.source_type, ref.source_id))
        self.setCurrentIndex(self.count() - 1)
        self._update_completer_from_items()

    def ensure_selected_ref(self) -> ExposedTargetRef | None:
        ref = self.current_ref()
        if ref is not None:
            return ref
        text = self.currentText().strip()
        if not text:
            return None
        # Exact match na položku v seznamu.
        for index in range(self.count()):
            if not self._is_selectable_index(index):
                continue
            if self.itemText(index).casefold() == text.casefold():
                data = self.itemData(index)
                if isinstance(data, tuple) and len(data) == 2:
                    self.setCurrentIndex(index)
                    return ExposedTargetRef(str(data[0]), int(data[1]))
        return None

    def _rebuild_items(
        self,
        *,
        filter_text: str,
        selected_ref: ExposedTargetRef | None,
    ) -> None:
        needle = filter_text.strip().casefold()
        current_text = self.currentText()
        self.clear()

        roles = czech_sorted(
            responsibility_role_service.get_all(include_inactive=False),
            key=lambda role: role.name.casefold(),
        )
        groups = czech_sorted(
            exposed_group_service.get_active_all(),
            key=lambda group: group.name.casefold(),
        )

        def matches(name: str) -> bool:
            return not needle or needle in name.casefold()

        role_items = [role for role in roles if matches(role.name)]
        group_items = [group for group in groups if matches(group.name)]

        if role_items:
            self._add_header(SECTION_LABEL_ROLES)
            for role in role_items:
                self.addItem(role.name, (SOURCE_TYPE_ROLE, int(role.id)))

        if group_items:
            self._add_header(SECTION_LABEL_HAZARD_GROUPS)
            for group in group_items:
                self.addItem(group.name, (SOURCE_TYPE_HAZARD_GROUP, int(group.id)))

        if selected_ref is not None and self._find_ref_index(selected_ref) < 0:
            from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
                resolve_exposed_target_display_name,
            )

            label = resolve_exposed_target_display_name(selected_ref)
            if matches(label):
                self.addItem(label, (selected_ref.source_type, selected_ref.source_id))

        self._update_completer_from_items()
        if current_text and self.current_ref() is None:
            self.setCurrentText(current_text)

    def _add_header(self, title: str) -> None:
        index = self.count()
        self.addItem(title, None)
        model = self.model()
        item = model.item(index) if hasattr(model, "item") else None
        if isinstance(item, QStandardItem):
            item.setEnabled(False)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def _find_ref_index(self, ref: ExposedTargetRef) -> int:
        for index in range(self.count()):
            data = self.itemData(index)
            if data == (ref.source_type, ref.source_id):
                return index
        return -1

    def _is_selectable_index(self, index: int) -> bool:
        data = self.itemData(index)
        return isinstance(data, tuple) and len(data) == 2

    def _update_completer_from_items(self) -> None:
        labels = [
            self.itemText(index)
            for index in range(self.count())
            if self._is_selectable_index(index)
        ]
        completer = QCompleter(labels, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
