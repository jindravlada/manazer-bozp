"""Editor šablony události."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.schuzky.constants import (
    DEFAULT_EVENT_TYPE,
    DEFAULT_MEETING_PRIORITY,
    MEETING_PRIORITIES,
    TEMPLATE_DIALOG_TITLE,
    TEMPLATE_NAME_REQUIRED,
    TEMPLATE_TAB_MAIN,
    TAB_DISCUSSION,
)
from moduly.schuzky.sluzby.meeting_event_type_service import meeting_event_type_service
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
from moduly.schuzky.ui.meeting_agenda_items_widget import MeetingAgendaItemsWidget
from moduly.schuzky.ui.meeting_location_typeahead import MeetingLocationTypeahead
from moduly.schuzky.ui.meeting_people_widgets import (
    MeetingOrganizerWidget,
    MeetingParticipantsWidget,
)


class MeetingTemplateDialog(QDialog):
    def __init__(self, parent=None, template=None):
        super().__init__(parent)
        self.template = template

        self.setWindowTitle(TEMPLATE_DIALOG_TITLE)
        self.resize(740, 680)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._main_tab(), TEMPLATE_TAB_MAIN)
        self.tabs.addTab(self._agenda_tab(), TAB_DISCUSSION)
        layout.addWidget(self.tabs, 1)

        # Spec: Zavřít + Uložit (Uložit i u rozpracované šablony).
        buttons = create_save_cancel_box(self, is_new=False)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if template is not None:
            self._load_template(template)
        else:
            self.agenda_items_widget.load_items([])

    def _main_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Název šablony")

        self.event_type_combo = QComboBox()
        self.event_type_combo.setEditable(False)
        for name in meeting_event_type_service.get_active_names():
            self.event_type_combo.addItem(name)
        if self.event_type_combo.findText(DEFAULT_EVENT_TYPE) >= 0:
            self.event_type_combo.setCurrentText(DEFAULT_EVENT_TYPE)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(list(MEETING_PRIORITIES))
        self.priority_combo.setCurrentText(DEFAULT_MEETING_PRIORITY)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název události")

        self.location_edit = MeetingLocationTypeahead()
        self.organizer_selector = MeetingOrganizerWidget()
        self.participants_selector = MeetingParticipantsWidget()

        form.addRow("Název šablony:", self.name_edit)
        form.addRow("Typ události:", self.event_type_combo)
        form.addRow("Priorita:", self.priority_combo)
        form.addRow("Název události:", self.title_edit)
        form.addRow("Místo:", self.location_edit)
        form.addRow("Organizátor:", self.organizer_selector)
        form.addRow("Účastníci:", self.participants_selector)
        return page

    def _agenda_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.agenda_items_widget = MeetingAgendaItemsWidget(template_mode=True)
        layout.addWidget(self.agenda_items_widget)
        return page

    def _load_template(self, template) -> None:
        self.name_edit.setText(template.name or "")

        event_type = meeting_event_type_service.normalize(
            getattr(template, "event_type", None)
        )
        if self.event_type_combo.findText(event_type) < 0:
            self.event_type_combo.addItem(event_type)
        self.event_type_combo.setCurrentText(event_type)

        priority = meeting_service.normalize_priority(getattr(template, "priority", None))
        if self.priority_combo.findText(priority) >= 0:
            self.priority_combo.setCurrentText(priority)

        self.title_edit.setText(template.title or "")
        self.location_edit.set_location_text(template.location or "")
        self.organizer_selector.set_person_id(template.organizer_person_id)
        self.participants_selector.set_participants(
            person_ids=meeting_template_service.parse_participant_ids(template),
            external_participants=meeting_template_service.parse_external_participants(
                template
            ),
        )
        self.agenda_items_widget.load_items(
            meeting_template_service.parse_agenda_items(template)
        )

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "event_type": self.event_type_combo.currentText().strip(),
            "title": self.title_edit.text().strip(),
            "location": self.location_edit.display_text(),
            "priority": self.priority_combo.currentText(),
            "organizer_person_id": self.organizer_selector.current_person_id(),
            "participant_ids": self.participants_selector.selected_person_ids(),
            "external_participants": self.participants_selector.external_participants(),
            "agenda_items": self.agenda_items_widget.get_items(),
        }

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, TEMPLATE_DIALOG_TITLE, TEMPLATE_NAME_REQUIRED)
            self.tabs.setCurrentIndex(0)
            self.name_edit.setFocus()
            return
        self.accept()
