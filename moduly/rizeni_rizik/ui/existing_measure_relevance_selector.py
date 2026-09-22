"""Zaškrtávací výběr „Platí pro“ omezený na skupiny/role nadřazeného posouzení."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QSizePolicy, QVBoxLayout, QWidget

from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    ExposedTargetRef,
    resolve_exposed_target_display_name,
)

EXISTING_MEASURE_ACTIVE_GAP_PX = 12
EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME = "existing_measure_active_gap"


class ExistingMeasureRelevanceSelector(QWidget):
    """Zobrazuje pouze skupiny/role aktuálního posouzení."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._checkboxes: list[tuple[ExposedTargetRef, QCheckBox]] = []

    def set_options(
        self,
        available: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
        selected: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checkboxes = []

        available_refs = list(available or ())
        if selected is None:
            selected_keys = {ref.key for ref in available_refs}
        else:
            selected_keys = {ref.key for ref in selected}

        for ref in available_refs:
            checkbox = QCheckBox(resolve_exposed_target_display_name(ref), self)
            checkbox.setChecked(ref.key in selected_keys)
            self._layout.addWidget(checkbox)
            self._checkboxes.append((ref, checkbox))

    def selected_refs(self) -> list[ExposedTargetRef]:
        return [ref for ref, checkbox in self._checkboxes if checkbox.isChecked()]

    def available_refs(self) -> list[ExposedTargetRef]:
        return [ref for ref, _checkbox in self._checkboxes]

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        for _ref, checkbox in self._checkboxes:
            checkbox.setEnabled(enabled)


def add_active_checkbox_separated(form: QFormLayout, checkbox: QCheckBox) -> QWidget:
    """Oddělí stav Aktivní od seznamu „Platí pro“ malým svislým odstupem."""
    gap = QWidget()
    gap.setObjectName(EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME)
    gap.setFixedHeight(EXISTING_MEASURE_ACTIVE_GAP_PX)
    gap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    form.addRow(gap)
    form.addRow("", checkbox)
    return gap
