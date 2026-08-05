"""Sdílené akce šablon událostí pro přehledy a editor."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.widgets.dialog_utils import exec_maximized
from moduly.schuzky.constants import (
    LIST_WINDOW_TITLE,
    TEMPLATE_SAVE_REQUIRES_MEETING,
    TEMPLATE_SAVE_SUCCESS,
)
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import MeetingValidationError, meeting_service
from moduly.schuzky.sluzby.meeting_template_service import (
    MeetingTemplateValidationError,
    meeting_template_service,
)
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_template_dialogs import (
    MeetingTemplatePickDialog,
    SaveMeetingTemplateDialog,
)


def save_meeting_as_template(parent: QWidget, dialog: MeetingDialog) -> bool:
    """Uloží pracovní obsah uložené Události jako šablonu."""
    if dialog.meeting is None or getattr(dialog.meeting, "id", None) is None:
        QMessageBox.information(parent, LIST_WINDOW_TITLE, TEMPLATE_SAVE_REQUIRES_MEETING)
        return False

    suggested = (dialog.title_edit.text() or "").strip()
    name_dialog = SaveMeetingTemplateDialog(parent, suggested_name=suggested)
    if name_dialog.exec() != name_dialog.DialogCode.Accepted:
        return False

    try:
        meeting_template_service.create_from_meeting_payload(
            template_name=name_dialog.template_name(),
            meeting_data=dialog.get_data(),
            agenda_items=dialog.get_agenda_items(),
        )
    except MeetingTemplateValidationError as error:
        QMessageBox.warning(parent, LIST_WINDOW_TITLE, str(error))
        return False

    QMessageBox.information(parent, LIST_WINDOW_TITLE, TEMPLATE_SAVE_SUCCESS)
    return True


def create_meeting_from_template(parent: QWidget) -> bool:
    """Výběr šablony → editor nové Události s předvyplněnými údaji."""
    pick = MeetingTemplatePickDialog(parent)
    if pick.exec() != pick.DialogCode.Accepted:
        return False
    template_id = pick.selected_template_id()
    if template_id is None:
        return False
    template = meeting_template_service.get_by_id(template_id)
    if template is None:
        QMessageBox.warning(parent, LIST_WINDOW_TITLE, "Šablona nebyla nalezena.")
        return False

    dialog = MeetingDialog(parent, template=template)
    if not exec_maximized(dialog):
        return False
    try:
        meeting = meeting_service.create_meeting(**dialog.get_data())
        meeting_agenda_item_service.save_items(meeting.id, dialog.get_agenda_items())
    except MeetingValidationError as error:
        QMessageBox.warning(parent, LIST_WINDOW_TITLE, str(error))
        return False
    return True
