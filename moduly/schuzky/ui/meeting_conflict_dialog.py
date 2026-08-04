"""Dialog časového konfliktu naplánovaných událostí."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from moduly.schuzky.constants import (
    CONFLICT_BTN_CANCEL,
    CONFLICT_BTN_EDIT,
    CONFLICT_BTN_SAVE,
    CONFLICT_DIALOG_TEXT,
    CONFLICT_DIALOG_TITLE,
)
from moduly.schuzky.sluzby.meeting_service import meeting_service

# Vlastní výsledky – neplést s QDialog.Accepted/Rejected.
CONFLICT_CHOICE_EDIT = 1
CONFLICT_CHOICE_SAVE = 2
CONFLICT_CHOICE_CANCEL = 0


class MeetingConflictDialog(QDialog):
    def __init__(self, conflicts, parent=None):
        super().__init__(parent)
        self.setWindowTitle(CONFLICT_DIALOG_TITLE)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(480)
        self._choice = CONFLICT_CHOICE_CANCEL

        layout = QVBoxLayout(self)

        intro = QLabel(CONFLICT_DIALOG_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        lines = []
        for meeting in conflicts:
            lines.append(f"• {meeting_service.format_conflict_line(meeting)}")
        detail = QLabel("\n".join(lines) if lines else "")
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(detail)

        buttons = QDialogButtonBox(self)
        edit_btn = QPushButton(CONFLICT_BTN_EDIT)
        save_btn = QPushButton(CONFLICT_BTN_SAVE)
        cancel_btn = QPushButton(CONFLICT_BTN_CANCEL)
        buttons.addButton(edit_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(save_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        edit_btn.setDefault(True)
        edit_btn.setAutoDefault(True)
        save_btn.setAutoDefault(False)
        cancel_btn.setAutoDefault(False)

        edit_btn.clicked.connect(self._on_edit)
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(buttons)

    @property
    def choice(self) -> int:
        return self._choice

    def _on_edit(self) -> None:
        self._choice = CONFLICT_CHOICE_EDIT
        self.done(CONFLICT_CHOICE_EDIT)

    def _on_save(self) -> None:
        self._choice = CONFLICT_CHOICE_SAVE
        self.done(CONFLICT_CHOICE_SAVE)

    def _on_cancel(self) -> None:
        self._choice = CONFLICT_CHOICE_CANCEL
        self.done(CONFLICT_CHOICE_CANCEL)
