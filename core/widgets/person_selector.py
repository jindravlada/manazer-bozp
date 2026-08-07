from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted, worker_sort_key
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.person_thp_link import find_thp_worker_for_person

ADD_NEW_PERSON = object()
ADD_NEW_PERSON_LABEL = "➕ Přidat novou osobu..."


class PersonSelector(SearchComboBox):
    def __init__(
        self,
        parent=None,
        include_empty: bool = True,
        allow_custom_value: bool = True,
        include_inactive: bool = False,
        allow_add_new: bool = True,
        exclude_thp_linked: bool = False,
    ):
        super().__init__(values=[], parent=parent, allow_custom_value=allow_custom_value)
        self.include_empty = include_empty
        self.include_inactive = include_inactive
        self.allow_add_new = allow_add_new
        self.exclude_thp_linked = exclude_thp_linked
        self._persons_by_id = {}
        self._preserve_person_id: int | None = None
        self._handling_add_new = False

        self.activated.connect(self._on_activated)
        self.reload()

    def _should_include_person(self, person, *, preserve_id: int | None) -> bool:
        if not self.exclude_thp_linked:
            return True
        if preserve_id is not None and person.id == preserve_id:
            return True
        return find_thp_worker_for_person(person) is None

    def reload(self, preserve_id: int | None = None) -> None:
        if preserve_id is not None:
            self._preserve_person_id = preserve_id

        current_text = self.currentText().strip()
        current_id = self._resolve_current_person_id()

        self.blockSignals(True)
        self.clear()
        self._persons_by_id = {}

        if self.include_empty:
            self.addItem("", None)

        persons = person_service.get_all(include_inactive=self.include_inactive)
        persons = czech_sorted(persons, key=worker_sort_key)
        keep_id = self._preserve_person_id or current_id

        names = []
        for person in persons:
            if not self._should_include_person(person, preserve_id=keep_id):
                continue
            self._append_person_item(person)
            names.append(person.display_name)

        preserve_id = self._preserve_person_id or current_id
        if preserve_id is not None and preserve_id not in self._persons_by_id:
            person = person_service.get_by_id(preserve_id)
            if person is not None:
                self._append_person_item(person, inactive_marker=not person.active)
                if person.display_name not in names:
                    names.append(person.display_name)

        if self.allow_add_new:
            self.addItem(ADD_NEW_PERSON_LABEL, ADD_NEW_PERSON)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if preserve_id is not None:
            self.set_person_id(preserve_id)
        elif current_text:
            self.setCurrentText(current_text)
        elif self.include_empty:
            self.setCurrentIndex(0)

        self.blockSignals(False)
        self._preserve_person_id = None

    def _append_person_item(self, person, *, inactive_marker: bool = False) -> None:
        label = person.display_name
        if inactive_marker or (not person.active and self.include_inactive):
            label = f"{label} (neaktivní)"
        self._persons_by_id[person.id] = person
        insert_index = self.count()
        if self.allow_add_new and self.count() > 0 and self.itemData(self.count() - 1) is ADD_NEW_PERSON:
            insert_index = self.count() - 1
        self.insertItem(insert_index, label, person.id)

    def _on_activated(self, index: int) -> None:
        if self._handling_add_new:
            return
        if self.itemData(index) is not ADD_NEW_PERSON:
            return

        self._handling_add_new = True
        try:
            from moduly.nastaveni.ui.person_dialog import PersonDialog

            previous_id = self._resolve_current_person_id()
            dialog = PersonDialog(self)
            if dialog.exec():
                data = dialog.get_data()
                if data["first_name"] and data["last_name"]:
                    person = person_service.create_person(**data)
                    self.reload(preserve_id=person.id)
                    self.set_person_id(person.id)
                    return

            if previous_id is not None:
                self.set_person_id(previous_id)
            elif self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentIndex(-1)
                self.setCurrentText("")
        finally:
            self._handling_add_new = False

    def _resolve_current_person_id(self) -> int | None:
        text = self.currentText().strip()
        for i in range(self.count()):
            if self.itemData(i) is ADD_NEW_PERSON:
                continue
            if self.itemText(i).strip() == text:
                data = self.itemData(i)
                return data if isinstance(data, int) else None
        return None

    def current_person_id(self) -> int | None:
        return self._resolve_current_person_id()

    def current_person(self):
        person_id = self.current_person_id()
        if person_id is None:
            return None
        person = self._persons_by_id.get(person_id)
        if person is not None:
            return person
        return person_service.get_by_id(person_id)

    def set_person_id(self, person_id: int | None) -> None:
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

        person = person_service.get_by_id(person_id)
        if person is not None:
            self._append_person_item(person, inactive_marker=not person.active)
            index = self.findData(person_id)
            if index >= 0:
                self.setCurrentIndex(index)
                return

        if self.include_empty:
            self.setCurrentIndex(0)
        else:
            self.setCurrentText("")

    def display_text(self) -> str:
        return self.currentText().strip()
