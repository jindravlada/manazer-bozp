"""Infrastruktura nabídky Nápověda pro budoucí menu hlavního okna."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from core.windows.changelog_dialog import ChangelogDialog

HELP_MENU_TITLE = "Nápověda"
VERSION_HISTORY_ACTION_TITLE = "Historie verzí"


def show_version_history(parent: QWidget | None = None) -> None:
    """Zobrazí oficiální CHANGELOG projektu."""
    ChangelogDialog(parent).exec()
