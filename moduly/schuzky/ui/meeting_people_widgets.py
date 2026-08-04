"""Výběr organizátora a účastníků události (THP + Osoby → person_id)."""

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

from core.utils.czech_sort import czech_sorted, person_display_name_sort_key, worker_sort_key
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.sluzby.meeting_person_link import (
    ensure_person_for_thp_worker,
    find_thp_worker_for_person,
    person_list_label,
)


class MeetingOrganizerWidget(QWidget):
    """Primárně THP; volitelně výběr z číselníku Osoby. Ukládá person_id."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._person_id: int | None = None
        self._suppress = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row = QHBoxLayout()
        self.thp_selector = ThpWorkerSelector(
            include_empty=True,
            allow_custom_value=False,
        )
        self.from_persons_btn = QPushButton("Vybrat z osob...")
        row.addWidget(self.thp_selector, 1)
        row.addWidget(self.from_persons_btn)
        layout.addLayout(row)

        self.person_label = QLabel("")
        self.person_label.setObjectName("MutedText")
        self.person_label.setVisible(False)
        layout.addWidget(self.person_label)

        self.thp_selector.currentIndexChanged.connect(self._on_thp_changed)
        self.from_persons_btn.clicked.connect(self._pick_from_persons)

    def current_person_id(self) -> int | None:
        return self._person_id

    def set_person_id(self, person_id: int | None) -> None:
        self._person_id = int(person_id) if person_id is not None else None
        self._sync_ui_from_person_id()

    def _on_thp_changed(self, *_args) -> None:
        if self._suppress:
            return
        worker = self.thp_selector.current_person()
        if worker is None:
            self._person_id = None
            self._update_person_label()
            return
        person = ensure_person_for_thp_worker(worker)
        self._person_id = person.id
        self._update_person_label()

    def _pick_from_persons(self) -> None:
        dialog = _SinglePersonPickDialog(self, current_id=self._person_id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._person_id = dialog.selected_person_id()
        self._sync_ui_from_person_id()

    def _sync_ui_from_person_id(self) -> None:
        self._suppress = True
        person = person_service.get_by_id(self._person_id)
        worker = find_thp_worker_for_person(person)
        if worker is not None:
            self.thp_selector.set_person_id(worker.id)
        else:
            self.thp_selector.set_person_id(None)
        self._suppress = False
        self._update_person_label()

    def _update_person_label(self) -> None:
        person = person_service.get_by_id(self._person_id)
        worker = self.thp_selector.current_person()
        if person is None:
            self.person_label.clear()
            self.person_label.setVisible(False)
            return
        if worker is not None:
            self.person_label.clear()
            self.person_label.setVisible(False)
            return
        self.person_label.setText(person_list_label(person))
        self.person_label.setVisible(True)


class MeetingParticipantsWidget(QWidget):
    """Jeden seznam účastníků; přidávání z THP i z Osob (person_id)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_thp_btn = QPushButton("Přidat THP")
        self.add_person_btn = QPushButton("Přidat osobu")
        self.remove_btn = QPushButton("Odebrat")
        toolbar.addWidget(self.add_thp_btn)
        toolbar.addWidget(self.add_person_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(90)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        self.add_thp_btn.clicked.connect(self._add_from_thp)
        self.add_person_btn.clicked.connect(self._add_from_persons)
        self.remove_btn.clicked.connect(self.remove_selected)

    def selected_person_ids(self) -> list[int]:
        return self._list_person_ids()

    def set_person_ids(self, person_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for person_id in person_ids or ():
            self._append_person_id(int(person_id))

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def _add_from_thp(self) -> None:
        dialog = _MultiThpPickDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for worker in dialog.selected_workers():
            person = ensure_person_for_thp_worker(worker)
            self._append_person_id(person.id)

    def _add_from_persons(self) -> None:
        dialog = _MultiPersonPickDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for person_id in dialog.selected_person_ids():
            self._append_person_id(person_id)

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


class _MultiThpPickDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přidat THP")
        self.resize(420, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Vyberte jednoho nebo více aktivních THP:"))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        workers = czech_sorted(
            settings_service.get_workers(include_inactive=False),
            key=worker_sort_key,
        )
        for worker in workers:
            item = QListWidgetItem(worker.display_name)
            item.setData(Qt.ItemDataRole.UserRole, worker.id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_workers(self):
        result = []
        for item in self.list_widget.selectedItems():
            worker_id = item.data(Qt.ItemDataRole.UserRole)
            worker = settings_service.get_worker_by_id(worker_id)
            if worker is not None:
                result.append(worker)
        return result


class _MultiPersonPickDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Přidat osobu")
        self.resize(420, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Vyberte jednu nebo více osob:"))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        people = czech_sorted(
            person_service.get_all(include_inactive=False),
            key=lambda person: person_display_name_sort_key(person.display_name),
        )
        for person in people:
            item = QListWidgetItem(person_list_label(person))
            item.setData(Qt.ItemDataRole.UserRole, person.id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_person_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.list_widget.selectedItems():
            raw = item.data(Qt.ItemDataRole.UserRole)
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        return ids
