"""Sdílené akce šablon událostí pro přehledy."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.widgets.dialog_utils import exec_maximized
from moduly.schuzky.constants import LIST_WINDOW_TITLE
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import MeetingValidationError, meeting_service
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog


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
