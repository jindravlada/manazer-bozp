"""Editor události – záložky Událost a Zápisky."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.nullable_date_edit import NullableDateEdit
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
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
from moduly.schuzky.ui.event_datetime_fields import EventDateTimeFields
from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
from moduly.schuzky.ui.meeting_conflict_dialog import (
    CONFLICT_CHOICE_EDIT,
    CONFLICT_CHOICE_SAVE,
    MeetingConflictDialog,
)
from moduly.schuzky.ui.meeting_location_typeahead import MeetingLocationTypeahead
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
    def __init__(self, parent=None, meeting=None, *, template=None):
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
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=meeting is None,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self._snapshot)
        self._editor.install_auto_dirty_tracking()
        self.starts_at_edit.dateTimeChanged.connect(self._editor.mark_dirty)
        self.ends_at_edit.dateTimeChanged.connect(self._editor.mark_dirty)
        self.remind_from_edit.dateChanged.connect(self._editor.mark_dirty)

        self.starts_at_edit.dateTimeChanged.connect(self._on_starts_changed)
        self.ends_at_edit.dateTimeChanged.connect(self._on_ends_changed)

        if meeting is not None:
            self._load_meeting(meeting)
        elif template is not None:
            self._load_template(template)
        else:
            self.agenda_items_widget.load_for_meeting(None)

        self._editor.capture_baseline()

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

        self.remind_from_edit = NullableDateEdit()
        _remind_hint = (
            "Od tohoto data se událost zobrazí na Pracovní ploše\nv části Připomínky."
        )
        self.remind_from_edit.setToolTip(_remind_hint)
        self.remind_from_hint = QLabel(_remind_hint)
        self.remind_from_hint.setWordWrap(True)
        self.remind_from_hint.setStyleSheet("color: #666;")

        self.location_edit = MeetingLocationTypeahead()
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
        form.addRow("Připomenout od:", self.remind_from_edit)
        form.addRow("", self.remind_from_hint)
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

        self.remind_from_edit.set_date_value(getattr(meeting, "remind_from", None))

        self.location_edit.set_location_text(meeting.location or "")
        self.organizer_selector.set_ref(meeting_service.organizer_ref(meeting))
        self.participants_selector.set_participants(
            participant_refs=meeting_service.parse_participant_refs(meeting),
            external_participants=meeting_service.parse_external_participants(meeting),
        )
        self.agenda_edit.setPlainText(meeting.agenda or "")
        priority = meeting_service.normalize_priority(getattr(meeting, "priority", None))
        if self.priority_combo.findText(priority) >= 0:
            self.priority_combo.setCurrentText(priority)
        status = meeting_service.normalize_status(meeting.status)
        if self.status_combo.findText(status) >= 0:
            self.status_combo.setCurrentText(status)

        self._legacy_proceedings = getattr(meeting, "proceedings", None) or ""
        self._legacy_conclusions = getattr(meeting, "conclusions", None) or ""
        self._legacy_notes = getattr(meeting, "notes", None) or ""

        self.agenda_items_widget.load_for_meeting(getattr(meeting, "id", None))

    def _load_template(self, template) -> None:
        data = meeting_template_service.meeting_data_from_template(template)
        event_type = meeting_event_type_service.normalize(data.get("event_type"))
        if self.event_type_combo.findText(event_type) < 0:
            self.event_type_combo.addItem(event_type)
        self.event_type_combo.setCurrentText(event_type)

        self.title_edit.setText(data.get("title") or "")

        self._suppress_datetime = True
        self.starts_at_edit.set_datetime(None)
        self.ends_at_edit.set_datetime(None)
        self._suppress_datetime = False
        self._ends_manually_edited = False
        self.remind_from_edit.clear_date()

        self.location_edit.set_location_text(data.get("location") or "")
        self.organizer_selector.set_ref(data.get("organizer_ref"))
        self.participants_selector.set_participants(
            participant_refs=data.get("participant_refs") or [],
            external_participants=data.get("external_participants") or [],
        )
        self.agenda_edit.setPlainText("")
        priority = meeting_service.normalize_priority(data.get("priority"))
        if self.priority_combo.findText(priority) >= 0:
            self.priority_combo.setCurrentText(priority)
        self.status_combo.setCurrentText(DEFAULT_MEETING_STATUS)

        self._legacy_proceedings = ""
        self._legacy_conclusions = ""
        self._legacy_notes = ""

        self.agenda_items_widget.load_items(
            meeting_template_service.parse_agenda_items(template)
        )

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "event_type": self.event_type_combo.currentText().strip(),
            "starts_at": self.starts_at_edit.get_datetime(),
            "ends_at": self.ends_at_edit.get_datetime(),
            "remind_from": self.remind_from_edit.get_date(),
            "location": self.location_edit.display_text(),
            "organizer_ref": self.organizer_selector.current_ref(),
            "participant_refs": self.participants_selector.selected_refs(),
            "external_participants": self.participants_selector.external_participants(),
            "agenda": self.agenda_edit.toPlainText(),
            "status": self.status_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "proceedings": self._legacy_proceedings,
            "conclusions": self._legacy_conclusions,
            "notes": self._legacy_notes,
        }

    def _snapshot(self) -> tuple:
        return (self.get_data(), self.get_agenda_items())

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

    def _validate(self) -> bool:
        data = self.get_data()
        try:
            meeting_service.validate_times(data["starts_at"], data["ends_at"])
        except ValueError:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, END_BEFORE_START_MESSAGE)
            return False

        remind_error = meeting_service.validate_remind_from(
            data.get("remind_from"),
            data.get("starts_at"),
        )
        if remind_error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, remind_error)
            return False

        if meeting_service.is_planned_start_in_past_forbidden(
            status=data["status"],
            starts_at=data["starts_at"],
            existing=self.meeting,
        ):
            self._show_past_start_blocked()
            return False

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
                    return False
                if choice != CONFLICT_CHOICE_SAVE:
                    return False
                # Uložit přesto – konflikt není chyba; další uložení kontrolu zopakuje.

        return True

    def accept(self) -> None:
        if not self._validate():
            return
        super().accept()
