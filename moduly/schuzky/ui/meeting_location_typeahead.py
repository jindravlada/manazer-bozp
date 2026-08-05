"""Našeptávač místa události z hierarchie pracovišť (volný zápis povolen)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.settings_service import settings_service

LOCATION_PATH_SEPARATOR = " → "


def workplace_location_path(workplace, by_id: dict) -> str:
    """Celá cesta Provoz → Pracoviště → Část (aktivní rodiče)."""
    parts: list[str] = []
    current = workplace
    seen: set[int] = set()
    while current is not None:
        wid = int(current.id)
        if wid in seen:
            break
        seen.add(wid)
        name = (current.name or "").strip()
        if name:
            parts.append(name)
        parent_id = getattr(current, "parent_id", None)
        current = by_id.get(parent_id) if parent_id is not None else None
    parts.reverse()
    return LOCATION_PATH_SEPARATOR.join(parts)


def build_workplace_location_suggestions(
    workplaces=None,
) -> list[tuple[str, int]]:
    """
    Aktivní položky hierarchie s celou cestou.

    Vrací (label, workplace_id) v pořadí stromu z get_workplaces.
    """
    items = list(workplaces if workplaces is not None else settings_service.get_workplaces(False))
    by_id = {int(item.id): item for item in items}
    suggestions: list[tuple[str, int]] = []
    seen_labels: set[str] = set()
    for workplace in items:
        label = workplace_location_path(workplace, by_id)
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        suggestions.append((label, int(workplace.id)))
    return suggestions


class MeetingLocationTypeahead(SearchComboBox):
    """Našeptávač místa: cesty pracovišť + libovolný vlastní text."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=True)
        self.setPlaceholderText("Místo konání")
        self.setMinimumContentsLength(28)
        self.reload()

    def reload(self) -> None:
        current = self.display_text()
        self.blockSignals(True)
        self.clear()

        names: list[str] = []
        for label, workplace_id in build_workplace_location_suggestions():
            self.addItem(label, workplace_id)
            names.append(label)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current:
            self.set_location_text(current)
        else:
            self.setCurrentText("")

        self.blockSignals(False)

    def display_text(self) -> str:
        return self.currentText().strip()

    def set_location_text(self, value: str | None) -> None:
        text = (value or "").strip()
        if not text:
            self.setCurrentText("")
            return
        for i in range(self.count()):
            if self.itemText(i).strip() == text:
                self.setCurrentIndex(i)
                return
        self.setCurrentText(text)

    def current_workplace_id(self) -> int | None:
        """ID jen při přesné shodě s nabídnutou cestou (vlastní text → None)."""
        text = self.display_text()
        if not text:
            return None
        for i in range(self.count()):
            if self.itemText(i).strip() == text:
                data = self.itemData(i)
                return data if isinstance(data, int) else None
        return None
