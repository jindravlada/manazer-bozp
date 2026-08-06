"""Sdílené akce šablon událostí pro přehledy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_close_box, exec_maximized
from moduly.schuzky.constants import LIST_WINDOW_TITLE, TEMPLATE_LIST_TITLE
from moduly.schuzky.sluzby.meeting_agenda_item_service import meeting_agenda_item_service
from moduly.schuzky.sluzby.meeting_service import MeetingValidationError, meeting_service
from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
from moduly.schuzky.ui.meeting_dialog import MeetingDialog
from moduly.schuzky.ui.meeting_template_dialogs import MeetingTemplatePickDialog
from moduly.schuzky.ui.meeting_templates_page import MeetingTemplatesPage

_templates_window: QDialog | None = None


class MeetingTemplatesWindow(QDialog):
    """Samostatné neblokující okno správy šablon událostí."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TEMPLATE_LIST_TITLE)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(960, 640)

        layout = QVBoxLayout(self)
        self.page = MeetingTemplatesPage()
        layout.addWidget(self.page, 1)

        buttons = create_close_box(self)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)


def open_meeting_templates_window(
    parent: QWidget | None = None,
    *,
    on_changed=None,
    on_closed=None,
) -> MeetingTemplatesWindow:
    """Otevře správu šablon jako neblokující okno (show, ne exec)."""
    global _templates_window

    def _connect_closed(window: MeetingTemplatesWindow) -> None:
        if not callable(on_closed):
            return
        window.finished.connect(
            on_closed,
            Qt.ConnectionType.SingleShotConnection,
        )

    def _connect_changed(window: MeetingTemplatesWindow) -> None:
        if not callable(on_changed):
            return
        window.page.templates_changed.connect(
            on_changed,
            Qt.ConnectionType.UniqueConnection,
        )

    if _templates_window is not None and _templates_window.isVisible():
        _templates_window.raise_()
        _templates_window.activateWindow()
        _connect_changed(_templates_window)
        _connect_closed(_templates_window)
        return _templates_window

    window = MeetingTemplatesWindow(parent)

    def _clear(*_args) -> None:
        global _templates_window
        if _templates_window is window:
            _templates_window = None

    window.destroyed.connect(_clear)
    _connect_changed(window)
    _connect_closed(window)

    _templates_window = window
    window.show()
    window.raise_()
    window.activateWindow()
    return window


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
