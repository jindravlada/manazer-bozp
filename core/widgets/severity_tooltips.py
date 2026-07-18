"""UI helpery pro tooltipy závažnosti (společné napříč moduly)."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidgetItem

from core.shared.risk_severity import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_LABELS,
    format_risk_severity_description,
    format_risk_severity_tooltip,
)
from core.widgets.info_tooltip import set_widget_tooltip


class _SupportsToolTip(Protocol):
    def setToolTip(self, text: str) -> None: ...


def apply_severity_tooltip(
    target: _SupportsToolTip | QTableWidgetItem,
    severity: str | None,
) -> None:
    """Nastaví tooltip závažnosti na buňku tabulky nebo jiný widget."""
    text = format_risk_severity_tooltip(severity or "")
    if text:
        set_widget_tooltip(target, text)
    else:
        target.setToolTip("")


def populate_severity_combo(
    combo: QComboBox,
    *,
    current: str | None = None,
    default: str = DEFAULT_RISK_SEVERITY,
) -> None:
    """Naplní ComboBox úrovněmi závažnosti včetně tooltipů položek."""
    combo.blockSignals(True)
    combo.clear()
    for severity in RISK_SEVERITIES:
        combo.addItem(RISK_SEVERITY_LABELS[severity], severity)
        index = combo.count() - 1
        tooltip = format_risk_severity_tooltip(severity)
        if tooltip:
            combo.setItemData(index, tooltip, Qt.ItemDataRole.ToolTipRole)
    selected = current if current in RISK_SEVERITIES else default
    index = combo.findData(selected)
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.blockSignals(False)
    sync_severity_combo_tooltip(combo)


def sync_severity_combo_tooltip(combo: QComboBox) -> None:
    """Tooltip zavřeného ComboBoxu = popis aktuálně vybrané úrovně."""
    apply_severity_tooltip(combo, combo.currentData())


def bind_severity_combo_tooltip(combo: QComboBox) -> None:
    """Po změně výběru aktualizuje tooltip ComboBoxu."""
    combo.currentIndexChanged.connect(lambda *_: sync_severity_combo_tooltip(combo))
    sync_severity_combo_tooltip(combo)


def severity_description_for_combo(combo: QComboBox) -> str:
    """Text popisu pod ComboBoxem (stejný zdroj jako tooltip)."""
    return format_risk_severity_description(combo.currentData() or "")
