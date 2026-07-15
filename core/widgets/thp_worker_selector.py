from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted, person_display_name_sort_key, worker_sort_key
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.settings_service import settings_service


class ThpWorkerSelector(SearchComboBox):
    """
    Výběr THP pracovníka z nastavení.

    Chování:
    - rozbalovací šipka se seznamem THP pracovníků,
    - možnost psát ručně,
    - našeptávání podle části textu bez ohledu na velikost písmen,
    - zachování interního ID pracovníka při výběru ze seznamu.
    """

    def __init__(self, parent=None, include_empty: bool = True, allow_custom_value: bool = True):
        super().__init__(values=[], parent=parent, allow_custom_value=allow_custom_value)
        self.include_empty = include_empty
        self._workers_by_id = {}
        self.reload()

    def reload(self):
        current_text = self.currentText().strip()
        current_id = self.currentData()

        self.clear()
        self._workers_by_id = {}

        if self.include_empty:
            self.addItem("", None)

        workers = settings_service.get_workers(include_inactive=False)
        workers = czech_sorted(workers, key=worker_sort_key)

        names = []
        for worker in workers:
            name = getattr(worker, "display_name", "") or ""
            if not name:
                continue
            self._workers_by_id[worker.id] = worker
            self.addItem(name, worker.id)
            names.append(name)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current_id is not None:
            self.set_person_id(current_id)
        elif current_text:
            self.setCurrentText(current_text)
        elif self.include_empty:
            self.setCurrentIndex(0)

    def current_person_id(self):
        data = self.currentData()
        if isinstance(data, int):
            return data

        text = self.currentText().strip()
        for i in range(self.count()):
            if self.itemText(i).strip() == text:
                item_data = self.itemData(i)
                return item_data if isinstance(item_data, int) else None
        return None

    def current_person(self):
        person_id = self.current_person_id()
        return self._workers_by_id.get(person_id)

    def set_person_id(self, person_id):
        if person_id is None:
            if self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentText("")
            return

        index = self.findData(person_id)
        if index >= 0:
            self.setCurrentIndex(index)
            return

        worker = settings_service.get_worker_by_id(person_id)
        if worker is not None:
            label = worker.display_name
            if not worker.active:
                label = f"{label} (neaktivní)"
            self._workers_by_id[worker.id] = worker
            self.addItem(label, worker.id)
            self.setCurrentIndex(self.count() - 1)
            return

        if self.include_empty:
            self.setCurrentIndex(0)
        else:
            self.setCurrentText("")


def sorted_person_names(names: list[str]) -> list[str]:
    return czech_sorted(names, key=person_display_name_sort_key)
