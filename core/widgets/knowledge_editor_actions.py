"""Sdílené ovládání editorů metodiky Auditů a Prověrek."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QWidget,
)

KNOWLEDGE_EDITOR_APPLY_LABEL = "Použít"
KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL = "Uložit a zavřít"
KNOWLEDGE_EDITOR_CLOSE_LABEL = "Zavřít"
KNOWLEDGE_EDITOR_SAVED_MESSAGE = "✓ Uloženo."
KNOWLEDGE_EDITOR_UNSAVED_MESSAGE = "● Neuložené změny"
KNOWLEDGE_EDITOR_UNSAVED_PROMPT = "Uložit změny před zavřením?"
KNOWLEDGE_EDITOR_SAVE_LABEL = "Uložit"
KNOWLEDGE_EDITOR_DISCARD_LABEL = "Neukládat"
KNOWLEDGE_EDITOR_CANCEL_LABEL = "Zrušit"


def _standard_icon(pixmap: QStyle.StandardPixmap) -> QIcon:
    return QApplication.style().standardIcon(pixmap)


def _configure_apply_button(button: QPushButton) -> None:
    button.setText(KNOWLEDGE_EDITOR_APPLY_LABEL)
    icon = _standard_icon(QStyle.StandardPixmap.SP_DialogApplyButton)
    if icon.isNull():
        icon = _standard_icon(QStyle.StandardPixmap.SP_DialogOkButton)
    button.setIcon(icon)


def _configure_save_close_button(button: QPushButton) -> None:
    button.setText(KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL)
    button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))


def _configure_close_button(button: QPushButton) -> None:
    button.setText(KNOWLEDGE_EDITOR_CLOSE_LABEL)
    button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCloseButton))


def _configure_action_button(button: QPushButton) -> None:
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


def create_knowledge_editor_footer(
    *,
    on_apply: Callable[[], None],
    on_save_close: Callable[[], None],
    on_close: Callable[[], None],
    apply_enabled: bool = True,
) -> tuple[QHBoxLayout, QPushButton, QPushButton, QPushButton, QLabel]:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    status_label = QLabel("")
    status_label.setObjectName("InfoText")
    status_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

    apply_btn = QPushButton()
    save_close_btn = QPushButton()
    close_btn = QPushButton()

    _configure_apply_button(apply_btn)
    _configure_save_close_button(save_close_btn)
    _configure_close_button(close_btn)

    for button in (apply_btn, save_close_btn, close_btn):
        _configure_action_button(button)

    apply_btn.setEnabled(apply_enabled)
    apply_btn.clicked.connect(on_apply)
    save_close_btn.clicked.connect(on_save_close)
    close_btn.clicked.connect(on_close)

    layout.addWidget(status_label, 0)
    layout.addStretch(1)
    layout.addWidget(apply_btn, 0)
    layout.addWidget(save_close_btn, 0)
    layout.addWidget(close_btn, 0)

    return layout, apply_btn, save_close_btn, close_btn, status_label


def confirm_close_with_unsaved_changes(parent: QWidget, *, title: str) -> str:
    """Vrátí ``save``, ``discard`` nebo ``cancel``."""
    message = QMessageBox(parent)
    message.setWindowTitle(title)
    message.setText(KNOWLEDGE_EDITOR_UNSAVED_PROMPT)
    message.setIcon(QMessageBox.Icon.Question)

    save_btn = message.addButton(
        KNOWLEDGE_EDITOR_SAVE_LABEL,
        QMessageBox.ButtonRole.AcceptRole,
    )
    discard_btn = message.addButton(
        KNOWLEDGE_EDITOR_DISCARD_LABEL,
        QMessageBox.ButtonRole.DestructiveRole,
    )
    cancel_btn = message.addButton(
        KNOWLEDGE_EDITOR_CANCEL_LABEL,
        QMessageBox.ButtonRole.RejectRole,
    )
    message.setDefaultButton(cancel_btn)

    message.exec()
    clicked = message.clickedButton()
    if clicked is save_btn:
        return "save"
    if clicked is discard_btn:
        return "discard"
    return "cancel"


def show_unsaved_status(status_label: QLabel) -> None:
    status_label.setText(KNOWLEDGE_EDITOR_UNSAVED_MESSAGE)


def show_save_status(status_label: QLabel, *, message: str = KNOWLEDGE_EDITOR_SAVED_MESSAGE) -> None:
    status_label.setText(message)


def clear_save_status(status_label: QLabel) -> None:
    status_label.setText("")
