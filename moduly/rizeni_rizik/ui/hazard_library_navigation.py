"""Navigace do katalogu zdrojů rizik z jiných modulů."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def open_hazard_library_template(parent: QWidget | None, template_id: int) -> bool:
    window = parent.window() if parent is not None else None
    if window is None:
        return False
    opener = getattr(window, "open_hazard_library_template", None)
    if opener is None:
        return False
    opener(template_id)
    return True
