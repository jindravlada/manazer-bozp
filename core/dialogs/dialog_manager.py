"""Jednotné API pro informační / varovná / chybová / potvrzovací hlášení."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from core.dialogs.message_box import (
    show_critical,
    show_information,
    show_question,
    show_warning,
)


class DialogManager:
    """Tenký fasádní obal nad jednotnými QMessageBox helpery (UX-DIALOG-1)."""

    @staticmethod
    def info(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
        return show_information(parent, title, text)

    @staticmethod
    def warning(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
        return show_warning(parent, title, text)

    @staticmethod
    def error(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
        return show_critical(parent, title, text)

    @staticmethod
    def confirm(
        parent: QWidget | None,
        title: str,
        text: str,
        *,
        default_no: bool = True,
    ) -> bool:
        default = (
            QMessageBox.StandardButton.No
            if default_no
            else QMessageBox.StandardButton.Yes
        )
        return (
            show_question(
                parent,
                title,
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                default,
            )
            == QMessageBox.StandardButton.Yes
        )
