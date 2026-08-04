"""Editor schůzky – záložka Schůzka (MEETINGS-1a)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.multi_person_selector import MultiPersonSelector
from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
from core.widgets.person_selector import PersonSelector
from moduly.schuzky.constants import (
    DEFAULT_MEETING_STATUS,
    DIALOG_WINDOW_TITLE,
    END_BEFORE_START_MESSAGE,
    MEETING_STATUSES,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service


class MeetingDialog(QDialog):
    def __init__(self, parent=None, meeting=None):
        super().__init__(parent)
        self.meeting = meeting
        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        self.resize(720, 640)

        layout = QVBoxLayout(self)

        group = QGroupBox("Schůzka")
        form = QFormLayout(group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název schůzky")

        self.starts_at_edit = NullableDateTimeEdit()
        self.ends_at_edit = NullableDateTimeEdit()

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Místo konání")

        self.organizer_selector = PersonSelector(include_empty=True, allow_add_new=True)
        self.participants_selector = MultiPersonSelector()

        self.agenda_edit = QTextEdit()
        self.agenda_edit.setPlaceholderText("Program / poznámka")
        self.agenda_edit.setAcceptRichText(False)
        # Běžné textové pole – přibližně 4–6 řádků.
        self.agenda_edit.setMinimumHeight(110)

        self.status_combo = QComboBox()
        self.status_combo.addItems(list(MEETING_STATUSES))
        self.status_combo.setCurrentText(DEFAULT_MEETING_STATUS)

        form.addRow("Název:", self.title_edit)
        form.addRow("Datum a čas zahájení:", self.starts_at_edit)
        form.addRow("Datum a čas ukončení:", self.ends_at_edit)
        form.addRow("Místo:", self.location_edit)
        form.addRow("Organizátor:", self.organizer_selector)
        form.addRow("Účastníci:", self.participants_selector)
        form.addRow("Program / poznámka:", self.agenda_edit)
        form.addRow("Stav:", self.status_combo)

        layout.addWidget(group)

        buttons = create_save_cancel_box(self, is_new=meeting is None)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if meeting is not None:
            self._load_meeting(meeting)

    def _load_meeting(self, meeting) -> None:
        self.title_edit.setText(meeting.title or "")
        self.starts_at_edit.set_datetime(meeting.starts_at)
        self.ends_at_edit.set_datetime(meeting.ends_at)
        self.location_edit.setText(meeting.location or "")
        self.organizer_selector.set_person_id(meeting.organizer_person_id)
        self.participants_selector.set_person_ids(
            meeting_service.parse_participant_ids(meeting)
        )
        self.agenda_edit.setPlainText(meeting.agenda or "")
        status = meeting.status or DEFAULT_MEETING_STATUS
        if self.status_combo.findText(status) >= 0:
            self.status_combo.setCurrentText(status)

    def get_data(self) -> dict:
        return {
            "title": self.title_edit.text().strip(),
            "starts_at": self.starts_at_edit.get_datetime(),
            "ends_at": self.ends_at_edit.get_datetime(),
            "location": self.location_edit.text().strip(),
            "organizer_person_id": self.organizer_selector.current_person_id(),
            "participant_ids": self.participants_selector.selected_person_ids(),
            "agenda": self.agenda_edit.toPlainText(),
            "status": self.status_combo.currentText(),
        }

    def _on_accept(self) -> None:
        data = self.get_data()
        try:
            meeting_service.validate_times(data["starts_at"], data["ends_at"])
        except ValueError:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, END_BEFORE_START_MESSAGE)
            return
        self.accept()
