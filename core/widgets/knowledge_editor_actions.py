"""Sdílené ovládání editorů metodiky Auditů a Prověrek."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

KNOWLEDGE_EDITOR_APPLY_LABEL = "Použít"
KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL = "Uložit a zavřít"
KNOWLEDGE_EDITOR_CLOSE_LABEL = "Zavřít"
KNOWLEDGE_EDITOR_SAVED_MESSAGE = "Uloženo."
KNOWLEDGE_EDITOR_UNSAVED_PROMPT = "Uložit změny před zavřením?"


def create_knowledge_editor_footer(
    *,
    on_apply: Callable[[], None],
    on_save_close: Callable[[], None],
    on_close: Callable[[], None],
    apply_enabled: bool = True,
) -> tuple[QHBoxLayout, QPushButton, QPushButton, QPushButton, QLabel]:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)

    status_label = QLabel()
    status_label.setObjectName("InfoText")
    status_label.setVisible(False)

    apply_btn = QPushButton(KNOWLEDGE_EDITOR_APPLY_LABEL)
    save_close_btn = QPushButton(KNOWLEDGE_EDITOR_SAVE_CLOSE_LABEL)
    close_btn = QPushButton(KNOWLEDGE_EDITOR_CLOSE_LABEL)

    apply_btn.setEnabled(apply_enabled)
    apply_btn.clicked.connect(on_apply)
    save_close_btn.clicked.connect(on_save_close)
    close_btn.clicked.connect(on_close)

    layout.addWidget(status_label, 1)
    layout.addWidget(apply_btn)
    layout.addWidget(save_close_btn)
    layout.addWidget(close_btn)

    return layout, apply_btn, save_close_btn, close_btn, status_label


def confirm_close_with_unsaved_changes(parent: QWidget, *, title: str) -> str:
    """Vrátí ``save``, ``discard`` nebo ``cancel``."""
    message = QMessageBox(parent)
    message.setWindowTitle(title)
    message.setText(KNOWLEDGE_EDITOR_UNSAVED_PROMPT)
    message.setIcon(QMessageBox.Icon.Question)

    yes_btn = message.addButton("Ano", QMessageBox.ButtonRole.YesRole)
    no_btn = message.addButton("Ne", QMessageBox.ButtonRole.NoRole)
    cancel_btn = message.addButton("Storno", QMessageBox.ButtonRole.RejectRole)
    message.setDefaultButton(cancel_btn)

    message.exec()
    clicked = message.clickedButton()
    if clicked is yes_btn:
        return "save"
    if clicked is no_btn:
        return "discard"
    return "cancel"


def show_save_status(status_label: QLabel, *, message: str = KNOWLEDGE_EDITOR_SAVED_MESSAGE) -> None:
    status_label.setText(message)
    status_label.setVisible(True)


def clear_save_status(status_label: QLabel) -> None:
    status_label.clear()
    status_label.setVisible(False)
