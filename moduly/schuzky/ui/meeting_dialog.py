"""Editor události – záložky Událost a Zápisky."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import (
    DEFAULT_EVENT_DURATION_HOURS,
    DEFAULT_EVENT_TYPE,
    DEFAULT_MEETING_PRIORITY,
    DEFAULT_MEETING_STATUS,
    DIALOG_WINDOW_TITLE,
    END_BEFORE_START_MESSAGE,
    MEETING_PRIORITIES,
    MEETING_STATUSES,
    PAST_PLANNED_BACK_BUTTON,
    PAST_PLANNED_START_MESSAGE,
    STATUS_PLANNED,
    TAB_DISCUSSION,
    TAB_MEETING,
)
from moduly.schuzky.sluzby.meeting_event_type_service import meeting_event_type_service
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.schuzky.ui.event_datetime_fields import EventDateTimeFields
from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
from moduly.schuzky.ui.meeting_conflict_dialog import (
    CONFLICT_CHOICE_EDIT,
    CONFLICT_CHOICE_SAVE,
    MeetingConflictDialog,
)
from moduly.schuzky.ui.meeting_people_widgets import (
    MeetingOrganizerWidget,
    MeetingParticipantsWidget,
)

DEFAULT_EVENT_DURATION = timedelta(hours=DEFAULT_EVENT_DURATION_HOURS)


def _plain_text_edit(*, placeholder: str, min_height: int) -> QTextEdit:
    edit = QTextEdit()
    edit.setPlaceholderText(placeholder)
    edit.setAcceptRichText(False)
    edit.setMinimumHeight(min_height)
    return edit


class MeetingDialog(QDialog):
    def __init__(self, parent=None, meeting=None):
        super().__init__(parent)
        self.meeting = meeting
        # Legacy textová pole zápisu – v UI se nezobrazují, při uložení se zachovají.
        self._legacy_proceedings = ""
        self._legacy_conclusions = ""
        self._legacy_notes = ""
        self._ends_manually_edited = False
        self._suppress_datetime = False

        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(740, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._meeting_tab(), TAB_MEETING)
        self.tabs.addTab(self._discussion_tab(), TAB_DISCUSSION)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self, is_new=meeting is None)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.starts_at_edit.dateTimeChanged.connect(self._on_starts_changed)
        self.ends_at_edit.dateTimeChanged.connect(self._on_ends_changed)

        if meeting is not None:
            self._load_meeting(meeting)
        else:
            self.agenda_items_widget.load_for_meeting(None)

    def _meeting_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.event_type_combo = QComboBox()
        self.event_type_combo.setEditable(False)
        for name in meeting_event_type_service.get_active_names():
            self.event_type_combo.addItem(name)
        if self.event_type_combo.findText(DEFAULT_EVENT_TYPE) >= 0:
            self.event_type_combo.setCurrentText(DEFAULT_EVENT_TYPE)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název události")

        self.starts_at_edit = EventDateTimeFields()
        self.ends_at_edit = EventDateTimeFields()

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Místo konání")

        self.organizer_selector = MeetingOrganizerWidget()
        self.participants_selector = MeetingParticipantsWidget()

        # Běžné textové pole – přibližně 4–6 řádků.
        self.agenda_edit = _plain_text_edit(
            placeholder="Program / poznámka",
            min_height=110,
        )

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(list(MEETING_PRIORITIES))
        self.priority_combo.setCurrentText(DEFAULT_MEETING_PRIORITY)

        self.status_combo = QComboBox()
        self.status_combo.addItems(list(MEETING_STATUSES))
        self.status_combo.setCurrentText(DEFAULT_MEETING_STATUS)

        form.addRow("Typ události:", self.event_type_combo)
        form.addRow("Priorita:", self.priority_combo)
        form.addRow("Název události:", self.title_edit)
        form.addRow("Datum zahájení:", self.starts_at_edit)
        form.addRow("Datum ukončení:", self.ends_at_edit)
        form.addRow("Místo:", self.location_edit)
        form.addRow("Organizátor:", self.organizer_selector)
        form.addRow("Účastníci:", self.participants_selector)
        form.addRow("Program / poznámka:", self.agenda_edit)
        form.addRow("Stav:", self.status_combo)
        return page

    def _discussion_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.agenda_items_widget = MeetingAgendaItemsWidget()
        layout.addWidget(self.agenda_items_widget)
        return page

    def _load_meeting(self, meeting) -> None:
        event_type = meeting_event_type_service.normalize(
            getattr(meeting, "event_type", None)
        )
        if self.event_type_combo.findText(event_type) < 0:
            self.event_type_combo.addItem(event_type)
        self.event_type_combo.setCurrentText(event_type)

        self.title_edit.setText(meeting.title or "")

        self._suppress_datetime = True
        self.starts_at_edit.set_datetime(meeting.starts_at)
        self.ends_at_edit.set_datetime(meeting.ends_at)
        self._suppress_datetime = False
        # Existující ukončení považujeme za vědomě nastavené (nepřepisovat).
        self._ends_manually_edited = meeting.ends_at is not None

        self.location_edit.setText(meeting.location or "")
        self.organizer_selector.set_person_id(meeting.organizer_person_id)
        self.participants_selector.set_person_ids(
            meeting_service.parse_participant_ids(meeting)
        )
        self.agenda_edit.setPlainText(meeting.agenda or "")
        priority = meeting_service.normalize_priority(getattr(meeting, "priority", None))
        if self.priority_combo.findText(priority) >= 0:
            self.priority_combo.setCurrentText(priority)
        status = meeting.status or DEFAULT_MEETING_STATUS
        if self.status_combo.findText(status) >= 0:
            self.status_combo.setCurrentText(status)

        self._legacy_proceedings = getattr(meeting, "proceedings", None) or ""
        self._legacy_conclusions = getattr(meeting, "conclusions", None) or ""
        self._legacy_notes = getattr(meeting, "notes", None) or ""

        self.agenda_items_widget.load_for_meeting(getattr(meeting, "id", None))

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "event_type": self.event_type_combo.currentText().strip(),
            "starts_at": self.starts_at_edit.get_datetime(),
            "ends_at": self.ends_at_edit.get_datetime(),
            "location": self.location_edit.text().strip(),
            "organizer_person_id": self.organizer_selector.current_person_id(),
            "participant_ids": self.participants_selector.selected_person_ids(),
            "agenda": self.agenda_edit.toPlainText(),
            "status": self.status_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "proceedings": self._legacy_proceedings,
            "conclusions": self._legacy_conclusions,
            "notes": self._legacy_notes,
        }

    def get_agenda_items(self) -> list[dict]:
        return self.agenda_items_widget.get_items()

    def _on_starts_changed(self) -> None:
        if self._suppress_datetime:
            return
        starts = self.starts_at_edit.get_datetime()
        if starts is None:
            return
        if self._ends_manually_edited:
            return
        self._suppress_datetime = True
        self.ends_at_edit.set_datetime(starts + DEFAULT_EVENT_DURATION)
        self._suppress_datetime = False

    def _on_ends_changed(self) -> None:
        if self._suppress_datetime:
            return
        self._ends_manually_edited = True

    def _focus_starts_at(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.starts_at_edit.date_edit.setFocus()

    def _show_past_start_blocked(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(DIALOG_WINDOW_TITLE)
        box.setText(PAST_PLANNED_START_MESSAGE)
        back = box.addButton(PAST_PLANNED_BACK_BUTTON, QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(back)
        box.exec()
        self._focus_starts_at()

    def _on_accept(self) -> None:
        data = self.get_data()
        try:
            meeting_service.validate_times(data["starts_at"], data["ends_at"])
        except ValueError:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, END_BEFORE_START_MESSAGE)
            return

        if meeting_service.is_planned_start_in_past_forbidden(
            status=data["status"],
            starts_at=data["starts_at"],
            existing=self.meeting,
        ):
            self._show_past_start_blocked()
            return

        if data["status"] == STATUS_PLANNED:
            exclude_id = getattr(self.meeting, "id", None) if self.meeting else None
            conflicts = meeting_service.find_planned_conflicts(
                starts_at=data["starts_at"],
                ends_at=data["ends_at"],
                exclude_id=exclude_id,
            )
            if conflicts:
                conflict_dialog = MeetingConflictDialog(conflicts, self)
                choice = conflict_dialog.exec()
                if choice == CONFLICT_CHOICE_EDIT:
                    self._focus_starts_at()
                    return
                if choice != CONFLICT_CHOICE_SAVE:
                    return
                # Uložit přesto – konflikt není chyba; další uložení kontrolu zopakuje.

        self.accept()
