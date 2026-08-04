"""Výběr organizátora a účastníků události (našeptávač THP + Osoby → person_id)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.utils.czech_sort import czech_sorted, person_display_name_sort_key
from core.widgets.person_selector import PersonSelector
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.sluzby.meeting_person_link import (
    ensure_person_for_thp_worker,
    person_list_label,
)
from PySide6.QtWidgets import QCompleter


class MeetingPersonTypeahead(SearchComboBox):
    """Našeptávač současně nad aktivními THP i Osobami; ukládá person_id."""

    def __init__(self, parent=None, *, include_empty: bool = True):
        super().__init__(values=[], parent=parent, allow_custom_value=False)
        self.include_empty = include_empty
        self._person_ids_by_label: dict[str, int] = {}
        self.reload()

    def reload(self) -> None:
        current_id = self.current_person_id()
        self.clear()
        self._person_ids_by_label = {}

        if self.include_empty:
            self.addItem("", None)

        seen_ids: set[int] = set()
        candidates: list[tuple[str, int]] = []

        for worker in settings_service.get_workers(include_inactive=False):
            person = ensure_person_for_thp_worker(worker)
            if person.id in seen_ids:
                continue
            seen_ids.add(person.id)
            candidates.append((worker.display_name or person.display_name, person.id))

        for person in person_service.get_all(include_inactive=False):
            if person.id in seen_ids:
                continue
            seen_ids.add(person.id)
            candidates.append((person.display_name, person.id))

        candidates = czech_sorted(
            candidates,
            key=lambda item: person_display_name_sort_key(item[0]),
        )

        names: list[str] = []
        for label, person_id in candidates:
            self._person_ids_by_label[label] = person_id
            self.addItem(label, person_id)
            names.append(label)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current_id is not None:
            self.set_person_id(current_id)
        elif self.include_empty:
            self.setCurrentIndex(0)

    def current_person_id(self) -> int | None:
        data = self.currentData()
        if isinstance(data, int):
            return data
        text = self.currentText().strip()
        person_id = self._person_ids_by_label.get(text)
        if person_id is not None:
            return person_id
        for i in range(self.count()):
            if self.itemText(i).strip() == text:
                item_data = self.itemData(i)
                return item_data if isinstance(item_data, int) else None
        return None

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
        if person is None:
            if self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentText("")
            return

        label = person.display_name
        if not person.active:
            label = f"{label} (neaktivní)"
        self._person_ids_by_label[label] = person.id
        self.addItem(label, person.id)
        self.setCurrentIndex(self.count() - 1)

    def clear_selection(self) -> None:
        if self.include_empty:
            self.setCurrentIndex(0)
        else:
            self.setCurrentText("")


class MeetingOrganizerWidget(QWidget):
    """Našeptávač (THP + Osoby) + volitelně výběr z číselníku Osoby."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.typeahead = MeetingPersonTypeahead(include_empty=True)
        self.from_persons_btn = QPushButton("Vybrat z osob...")
        layout.addWidget(self.typeahead, 1)
        layout.addWidget(self.from_persons_btn)

        # Zpětná kompatibilita testů UX-3.
        self.thp_selector = self.typeahead
        self.person_label = QLabel("")
        self.person_label.setVisible(False)

        self.from_persons_btn.clicked.connect(self._pick_from_persons)

    def current_person_id(self) -> int | None:
        return self.typeahead.current_person_id()

    def set_person_id(self, person_id: int | None) -> None:
        self.typeahead.set_person_id(person_id)

    def _pick_from_persons(self) -> None:
        dialog = _SinglePersonPickDialog(self, current_id=self.current_person_id())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.set_person_id(dialog.selected_person_id())


class MeetingParticipantsWidget(QWidget):
    """Jeden seznam účastníků; přidávání našeptávačem (THP + Osoby)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.typeahead = MeetingPersonTypeahead(include_empty=True)
        self.remove_btn = QPushButton("Odebrat")
        top.addWidget(self.typeahead, 1)
        top.addWidget(self.remove_btn)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(90)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        self.typeahead.activated.connect(self._on_typeahead_activated)
        line = self.typeahead.lineEdit()
        if line is not None:
            line.returnPressed.connect(self._add_current)
        self.remove_btn.clicked.connect(self.remove_selected)

        # Zpětná kompatibilita starších akcí.
        self.add_thp_btn = QPushButton("Přidat THP")
        self.add_person_btn = QPushButton("Přidat osobu")
        self.add_thp_btn.setVisible(False)
        self.add_person_btn.setVisible(False)

    def selected_person_ids(self) -> list[int]:
        return self._list_person_ids()

    def set_person_ids(self, person_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for person_id in person_ids or ():
            self._append_person_id(int(person_id))

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def _on_typeahead_activated(self, _index: int) -> None:
        self._add_current()

    def _add_current(self) -> None:
        person_id = self.typeahead.current_person_id()
        if person_id is None:
            return
        self._append_person_id(person_id)
        self.typeahead.clear_selection()

    def _list_person_ids(self) -> list[int]:
        ids: list[int] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw is None:
                continue
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        return ids

    def _append_person_id(self, person_id: int) -> None:
        if person_id in self._list_person_ids():
            return
        person = person_service.get_by_id(person_id)
        item = QListWidgetItem(person_list_label(person, fallback_id=person_id))
        item.setData(Qt.ItemDataRole.UserRole, int(person_id))
        self.list_widget.addItem(item)


class _SinglePersonPickDialog(QDialog):
    def __init__(self, parent=None, *, current_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Vybrat osobu")
        self.resize(420, 120)
        layout = QVBoxLayout(self)
        self.selector = PersonSelector(
            include_empty=True,
            allow_add_new=True,
            include_inactive=False,
        )
        if current_id is not None:
            self.selector.set_person_id(current_id)
        layout.addWidget(self.selector)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_person_id(self) -> int | None:
        return self.selector.current_person_id()
