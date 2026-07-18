"""Naplnění ComboBoxu kategorií zdrojů z číselníku."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    hazard_source_category_service,
)


def populate_hazard_source_category_combo(
    combo: QComboBox,
    *,
    current_code: str | None = None,
    include_inactive_current: bool = True,
) -> None:
    """
    Aktivní kategorie podle pořadí.
    Pokud je current_code neaktivní, zůstane ve výběru (editace existujícího zdroje).
    """
    combo.blockSignals(True)
    combo.clear()
    active = list(hazard_source_category_service.get_active_all())
    codes = {item.code for item in active}
    for item in active:
        combo.addItem(item.name, item.code)

    if (
        include_inactive_current
        and current_code
        and current_code not in codes
    ):
        current = hazard_source_category_service.get_by_code(current_code)
        label = (
            f"{current.name} (neaktivní)"
            if current is not None
            else f"{hazard_source_category_service.label_for(current_code)} (neaktivní)"
        )
        combo.insertItem(0, label, current_code)

    if current_code:
        index = combo.findData(current_code)
        if index >= 0:
            combo.setCurrentIndex(index)
    elif combo.count():
        combo.setCurrentIndex(0)
    combo.blockSignals(False)
