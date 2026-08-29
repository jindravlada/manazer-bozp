"""Výběr organizátora a účastníků události (THP + Osoby → source_type + source_id)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
from PySide6.QtWidgets import QCompleter

from core.utils.czech_sort import czech_sorted, person_display_name_sort_key
from core.widgets.person_selector import PersonSelector
from core.widgets.search_combo_box import SearchComboBox
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.person_thp_link import (
    find_thp_worker_for_person,
    person_list_label,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.constants import (
    ACTION_ADD_EXTERNAL_PARTICIPANT,
    ACTION_EDIT,
    ACTION_REMOVE,
)
from moduly.schuzky.sluzby.meeting_participant_ref import (
    MEETING_SOURCE_PERSON,
    MEETING_SOURCE_THP_WORKER,
    normalize_participant_ref,
    ref_key,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service


class MeetingPersonTypeahead(SearchComboBox):
    """Našeptávač nad aktivními THP i skutečnými Osobami; ukládá source_type + source_id.

    Read-only načtení: nevytváří Person záznamy z THP.
    """

    def __init__(self, parent=None, *, include_empty: bool = True):
        super().__init__(values=[], parent=parent, allow_custom_value=False)
        self.include_empty = include_empty
        self._refs_by_label: dict[str, dict] = {}
        self.reload()

    def reload(self) -> None:
        current = self.current_ref()
        self.clear()
        self._refs_by_label = {}

        if self.include_empty:
            self.addItem("", None)

        candidates: list[tuple[str, dict]] = []

        for worker in settings_service.get_workers(include_inactive=False):
            ref = {
                "source_type": MEETING_SOURCE_THP_WORKER,
                "source_id": int(worker.id),
            }
            label = worker.display_name or f"THP #{worker.id}"
            candidates.append((label, ref))

        for person in person_service.get_all(include_inactive=False):
            # Nezobrazovat mirror THP v persons – jen skutečné externí/samostatné osoby.
            if find_thp_worker_for_person(person) is not None:
                continue
            ref = {
                "source_type": MEETING_SOURCE_PERSON,
                "source_id": int(person.id),
            }
            candidates.append((person.display_name, ref))

        candidates = czech_sorted(
            candidates,
            key=lambda item: person_display_name_sort_key(item[0]),
        )

        names: list[str] = []
        for label, ref in candidates:
            self._refs_by_label[label] = ref
            self.addItem(label, ref)
            names.append(label)

        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if current is not None:
            self.set_ref(current)
        elif self.include_empty:
            self.setCurrentIndex(0)

    def current_ref(self) -> dict | None:
        data = self.currentData()
        ref = normalize_participant_ref(data) if data is not None else None
        if ref is not None:
            return ref
        text = self.currentText().strip()
        mapped = self._refs_by_label.get(text)
        return normalize_participant_ref(mapped) if mapped else None

    def current_person_id(self) -> int | None:
        """Zpětná kompatibilita: Person ID, pokud je zdroj person."""
        ref = self.current_ref()
        if ref is None or ref["source_type"] != MEETING_SOURCE_PERSON:
            return None
        return int(ref["source_id"])

    def set_ref(self, ref: dict | None) -> None:
        normalized = normalize_participant_ref(ref) if ref else None
        if normalized is None:
            if self.include_empty:
                self.setCurrentIndex(0)
            else:
                self.setCurrentText("")
            return

        for index in range(self.count()):
            item_ref = normalize_participant_ref(self.itemData(index))
            if item_ref and ref_key(item_ref) == ref_key(normalized):
                self.setCurrentIndex(index)
                return

        label = meeting_service.resolve_ref_display_name(normalized)
        self._refs_by_label[label] = normalized
        self.addItem(label, normalized)
        self.setCurrentIndex(self.count() - 1)

    def set_person_id(self, person_id: int | None) -> None:
        """Legacy: nastaví Person ref."""
        if person_id is None:
            self.set_ref(None)
            return
        self.set_ref(
            {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person_id)}
        )

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

        self.thp_selector = self.typeahead
        self.person_label = QLabel("")
        self.person_label.setVisible(False)

        self.from_persons_btn.clicked.connect(self._pick_from_persons)

    def current_ref(self) -> dict | None:
        return self.typeahead.current_ref()

    def current_person_id(self) -> int | None:
        return self.typeahead.current_person_id()

    def set_ref(self, ref: dict | None) -> None:
        self.typeahead.set_ref(ref)

    def set_person_id(self, person_id: int | None) -> None:
        self.typeahead.set_person_id(person_id)

    def _pick_from_persons(self) -> None:
        current = self.current_ref()
        current_person_id = (
            int(current["source_id"])
            if current and current["source_type"] == MEETING_SOURCE_PERSON
            else None
        )
        dialog = _SinglePersonPickDialog(self, current_id=current_person_id)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        person_id = dialog.selected_person_id()
        if person_id is None:
            self.set_ref(None)
        else:
            self.set_ref(
                {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person_id)}
            )


class MeetingParticipantsWidget(QWidget):
    """Jeden seznam účastníků; interní (THP/Osoby) + externí."""

    participantsChanged = Signal()

    _KIND_REF = "ref"
    _KIND_PERSON = "person"  # legacy payload
    _KIND_EXTERNAL = "external"

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.typeahead = MeetingPersonTypeahead(include_empty=True)
        self.add_external_btn = QPushButton(ACTION_ADD_EXTERNAL_PARTICIPANT)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.remove_btn = QPushButton(ACTION_REMOVE)
        top.addWidget(self.typeahead, 1)
        top.addWidget(self.add_external_btn)
        top.addWidget(self.edit_btn)
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
        self.add_external_btn.clicked.connect(self.add_external)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.add_thp_btn = QPushButton("Přidat THP")
        self.add_person_btn = QPushButton("Přidat osobu")
        self.add_thp_btn.setVisible(False)
        self.add_person_btn.setVisible(False)

    def selected_refs(self) -> list[dict]:
        return self._list_refs()

    def selected_person_ids(self) -> list[int]:
        return [
            int(ref["source_id"])
            for ref in self._list_refs()
            if ref["source_type"] == MEETING_SOURCE_PERSON
        ]

    def external_participants(self) -> list[dict]:
        return meeting_service.normalize_external_participants(self._list_externals())

    def set_person_ids(self, person_ids: list[int] | tuple[int, ...] | None) -> None:
        self.set_participants(person_ids=person_ids, external_participants=[])

    def set_participants(
        self,
        *,
        person_ids: list[int] | tuple[int, ...] | None = None,
        participant_refs: list[dict] | None = None,
        external_participants: list[dict] | None = None,
    ) -> None:
        self.list_widget.clear()
        if participant_refs is not None:
            for ref in participant_refs:
                self._append_ref(ref)
        else:
            for person_id in person_ids or ():
                self._append_ref(
                    {
                        "source_type": MEETING_SOURCE_PERSON,
                        "source_id": int(person_id),
                    }
                )
        for item in meeting_service.normalize_external_participants(
            external_participants
        ):
            self._append_external(item)

    def add_external(self) -> None:
        from moduly.schuzky.ui.external_participant_dialog import ExternalParticipantDialog

        dialog = ExternalParticipantDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        before = self.list_widget.count()
        self._append_external(dialog.get_data())
        if self.list_widget.count() > before:
            self.participantsChanged.emit()

    def edit_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if len(items) != 1:
            return
        self._edit_item(items[0])

    def remove_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        for item in items:
            self.list_widget.takeItem(self.list_widget.row(item))
        self.participantsChanged.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._edit_item(item)

    def _edit_item(self, item: QListWidgetItem) -> None:
        from moduly.schuzky.ui.external_participant_dialog import ExternalParticipantDialog

        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict) or payload.get("kind") != self._KIND_EXTERNAL:
            return
        data = dict(payload.get("data") or {})
        dialog = ExternalParticipantDialog(self, data=data)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = meeting_service.normalize_external_participants([dialog.get_data()])
        if not updated:
            return
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"kind": self._KIND_EXTERNAL, "data": updated[0]},
        )
        item.setText(meeting_service.external_participant_label(updated[0]))
        self.participantsChanged.emit()

    def _on_typeahead_activated(self, _index: int) -> None:
        self._add_current()

    def _add_current(self) -> None:
        ref = self.typeahead.current_ref()
        if ref is None:
            return
        before = self.list_widget.count()
        self._append_ref(ref)
        self.typeahead.clear_selection()
        if self.list_widget.count() > before:
            self.participantsChanged.emit()

    def _list_refs(self) -> list[dict]:
        refs: list[dict] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            payload = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict):
                continue
            kind = payload.get("kind")
            if kind == self._KIND_REF:
                ref = normalize_participant_ref(payload.get("ref"))
                if ref:
                    refs.append(ref)
            elif kind == self._KIND_PERSON:
                try:
                    refs.append(
                        {
                            "source_type": MEETING_SOURCE_PERSON,
                            "source_id": int(payload.get("person_id")),
                        }
                    )
                except (TypeError, ValueError):
                    continue
        return refs

    def _list_externals(self) -> list[dict]:
        result: list[dict] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            payload = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict) or payload.get("kind") != self._KIND_EXTERNAL:
                continue
            data = payload.get("data")
            if isinstance(data, dict):
                result.append(data)
        return result

    def _append_ref(self, ref: dict | None) -> None:
        normalized = normalize_participant_ref(ref)
        if normalized is None:
            return
        key = ref_key(normalized)
        if key in {ref_key(existing) for existing in self._list_refs()}:
            return
        label = meeting_service.resolve_ref_display_name(normalized)
        if normalized["source_type"] == MEETING_SOURCE_PERSON:
            person = person_service.get_by_id(normalized["source_id"])
            label = person_list_label(person, fallback_id=normalized["source_id"])
        elif normalized["source_type"] == MEETING_SOURCE_THP_WORKER:
            worker = settings_service.get_worker_by_id(normalized["source_id"])
            if worker is not None:
                parts = [worker.display_name]
                detail = (worker.position or "").strip()
                if detail:
                    parts.append(detail)
                label = " – ".join(parts)
        item = QListWidgetItem(label)
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"kind": self._KIND_REF, "ref": normalized},
        )
        self.list_widget.addItem(item)

    def _append_person_id(self, person_id: int) -> None:
        self._append_ref(
            {"source_type": MEETING_SOURCE_PERSON, "source_id": int(person_id)}
        )

    def _append_external(self, data: dict) -> None:
        normalized = meeting_service.normalize_external_participants([data])
        if not normalized:
            return
        payload = normalized[0]
        item = QListWidgetItem(meeting_service.external_participant_label(payload))
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"kind": self._KIND_EXTERNAL, "data": payload},
        )
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
            exclude_thp_linked=True,
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
