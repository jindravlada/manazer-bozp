from core.dialogs.dialog_manager import DialogManager
from core.dialogs.message_box import (
    configure_application_for_dialogs,
    install_unified_message_boxes,
    polish_message_box,
    show_critical,
    show_information,
    show_question,
    show_warning,
    strip_application_title_suffix,
)

__all__ = [
    "DialogManager",
    "configure_application_for_dialogs",
    "install_unified_message_boxes",
    "polish_message_box",
    "show_critical",
    "show_information",
    "show_question",
    "show_warning",
    "strip_application_title_suffix",
]
