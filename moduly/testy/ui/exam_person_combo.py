"""Našeptávač zaměstnance podle osobního čísla, příjmení a jména."""

from __future__ import annotations

from core.widgets.search_combo_box import SearchComboBox


class ExamPersonCombo(SearchComboBox):
    def __init__(self, parent=None):
        super().__init__(parent=parent, allow_custom_value=False)
        self._ids: dict[str, int] = {}

    def set_people(self, people: list) -> None:
        self._ids = {}
        labels: list[str] = []
        for person in people:
            number = str(person.personal_number or "").strip()
            label = f"{number} – {person.display_name}" if number else person.display_name
            key = label.casefold()
            if key in self._ids:
                label = f"{label} ({person.id})"
                key = label.casefold()
            self._ids[key] = int(person.id)
            labels.append(label)
        self.set_items(labels, include_empty=True)

    def person_id(self) -> int | None:
        return self._ids.get(self.currentText().strip().casefold())
