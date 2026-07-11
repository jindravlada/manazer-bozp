from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.settings_service import settings_service


class WorkplaceSelector(SearchComboBox):
    """Výběr pracoviště z číselníku s možností ručního zadání vlastního textu."""

    def __init__(self, parent=None, include_empty: bool = True, allow_custom_value: bool = True):
        super().__init__(values=[], parent=parent, allow_custom_value=allow_custom_value)
        self.include_empty = include_empty
        self.reload()

    def reload(self):
        current_text = self.currentText().strip()
        current_id = self._resolve_current_workplace_id()

        self.blockSignals(True)
        self.clear()

        if self.include_empty:
            self.addItem("", None)

        workplaces = settings_service.get_workplaces(include_inactive=False)
        workplaces = czech_sorted(workplaces, key=lambda workplace: workplace.name)

        names: list[str] = []
        for workplace in workplaces:
            self.addItem(workplace.name, workplace.id)
            names.append(workplace.name)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current_id is not None:
            self.set_workplace_id(current_id)
        elif current_text:
            self.setCurrentText(current_text)
        elif self.include_empty:
            self.setCurrentIndex(0)

        self.blockSignals(False)

    def _resolve_current_workplace_id(self) -> int | None:
        """ID jen při přesné shodě textu s položkou číselníku (ne při vlastním textu)."""
        text = self.currentText().strip()
        if not text:
            return None
        for i in range(self.count()):
            if self.itemText(i).strip() == text:
                data = self.itemData(i)
                return data if isinstance(data, int) else None
        return None

    def current_workplace_id(self):
        return self._resolve_current_workplace_id()

    def display_text(self) -> str:
        return self.currentText().strip()

    def set_workplace_id(self, workplace_id, workplace_name: str = ""):
        if workplace_id is None:
            name = str(workplace_name or "").strip()
            if name:
                self.setCurrentText(name)
                return
            if self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentText("")
            return

        workplace_id = int(workplace_id)
        index = self.findData(workplace_id)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        name = str(workplace_name or "").strip()
        if not name:
            workplace = settings_service.get_workplace_by_id(workplace_id)
            name = workplace.name if workplace else f"Pracoviště #{workplace_id}"

        insert_at = 1 if self.include_empty else 0
        self.blockSignals(True)
        self.insertItem(insert_at, name, workplace_id)
        self.setCurrentIndex(insert_at)
        self.blockSignals(False)

    def set_workplace(self, workplace_id=None, workplace_name: str = "") -> None:
        if workplace_id is not None:
            self.set_workplace_id(workplace_id, workplace_name)
            return

        name = str(workplace_name or "").strip()
        if not name:
            if self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentText("")
            return

        # Přesná shoda s číselníkem → vybrat položku; jinak zachovat vlastní text.
        for i in range(self.count()):
            if self.itemText(i).strip() == name and isinstance(self.itemData(i), int):
                self.setCurrentIndex(i)
                return

        self.setCurrentText(name)
