"""Našeptávač zaměstnance podle osobního čísla, příjmení a jména."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted, worker_sort_key
from core.widgets.search_combo_box import SearchComboBox


def exam_person_choice_label(person) -> str:
    """Příjmení | Jméno | Tituly | Osobní číslo. Prázdné části se vynechají."""
    last_name = str(getattr(person, "last_name", "") or "").strip()
    first_name = str(getattr(person, "first_name", "") or "").strip()
    before = str(getattr(person, "title_before", "") or "").strip().strip(",")
    after = str(getattr(person, "title_after", "") or "").strip()
    if after.startswith(","):
        after = after.lstrip(",").strip()
    titles = ", ".join(part for part in (before, after) if part)
    number = str(getattr(person, "personal_number", "") or "").strip()
    return " | ".join(part for part in (last_name, first_name, titles, number) if part)


class ExamPersonCombo(SearchComboBox):
    def __init__(self, parent=None):
        super().__init__(parent=parent, allow_custom_value=False)
        self._ids: dict[str, int] = {}
        self._blocked: dict[str, str] = {}

    def set_people(self, people: list, blocked: dict[int, str] | None = None) -> None:
        reasons = blocked or {}
        self._ids = {}
        self._blocked = {}
        labels: list[str] = []
        selectable: list[str] = []
        seen: set[str] = set()
        for person in czech_sorted(list(people), key=worker_sort_key):
            label = exam_person_choice_label(person) or person.display_name
            reason = str(reasons.get(int(person.id)) or "").strip()
            if reason:
                label = f"{label} ({reason})"
            key = label.casefold()
            if key in seen:
                label = f"{label} ({person.id})"
                key = label.casefold()
            seen.add(key)
            labels.append(label)
            if reason:
                self._blocked[key] = reason
            else:
                self._ids[key] = int(person.id)
                selectable.append(label)
        self.set_items(labels, include_empty=True)
        self._disable_blocked()
        self._limit_completer(selectable)

    def person_id(self) -> int | None:
        return self._ids.get(self.currentText().strip().casefold())

    def blocked_reason(self) -> str | None:
        return self._blocked.get(self.currentText().strip().casefold())

    def _disable_blocked(self) -> None:
        model = self.model()
        if not isinstance(model, QStandardItemModel):
            return
        for index in range(self.count()):
            if self.itemText(index).strip().casefold() not in self._blocked:
                continue
            item = model.item(index)
            if item is None:
                continue
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)

    def _limit_completer(self, labels: list[str]) -> None:
        completer = QCompleter([""] + labels, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
