"""Zaškrtávací výběr „Platí pro“ omezený na skupiny/role nadřazeného posouzení."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import wrap_in_scroll_area
from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    ExposedTargetRef,
    resolve_exposed_target_display_name,
)

EXISTING_MEASURE_ACTIVE_GAP_PX = 12
EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME = "existing_measure_active_gap"
EXISTING_MEASURE_RELEVANCE_LIST_MAX_HEIGHT = 230
EXISTING_MEASURE_RELEVANCE_SCROLL_OBJECT_NAME = "existing_measure_relevance_scroll"


class ExistingMeasureRelevanceSelector(QWidget):
    """Zobrazuje pouze skupiny/role aktuálního posouzení."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checkboxes: list[tuple[ExposedTargetRef, QCheckBox]] = []

        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)

        self._scroll = wrap_in_scroll_area(self._list_host)
        self._scroll.setObjectName(EXISTING_MEASURE_RELEVANCE_SCROLL_OBJECT_NAME)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._select_all = QPushButton("Označit vše")
        self._deselect_all = QPushButton("Odznačit vše")
        self._select_all.clicked.connect(lambda: self._set_all_checked(True))
        self._deselect_all.clicked.connect(lambda: self._set_all_checked(False))
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(self._select_all)
        actions.addWidget(self._deselect_all)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll)
        layout.addLayout(actions)

    def set_options(
        self,
        available: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
        selected: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None = None,
    ) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._checkboxes = []

        available_refs = list(available or ())
        if selected is None:
            selected_keys = {ref.key for ref in available_refs}
        else:
            selected_keys = {ref.key for ref in selected}

        for ref in available_refs:
            checkbox = QCheckBox(resolve_exposed_target_display_name(ref), self._list_host)
            checkbox.setChecked(ref.key in selected_keys)
            self._list_layout.addWidget(checkbox)
            self._checkboxes.append((ref, checkbox))
        self._fit_scroll_height()

    def selected_refs(self) -> list[ExposedTargetRef]:
        return [ref for ref, checkbox in self._checkboxes if checkbox.isChecked()]

    def available_refs(self) -> list[ExposedTargetRef]:
        return [ref for ref, _checkbox in self._checkboxes]

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        for _ref, checkbox in self._checkboxes:
            checkbox.setEnabled(enabled)

    def _set_all_checked(self, checked: bool) -> None:
        for _ref, checkbox in self._checkboxes:
            checkbox.setChecked(checked)

    def _fit_scroll_height(self) -> None:
        if not self._checkboxes:
            self._scroll.setMinimumHeight(0)
            self._scroll.setMaximumHeight(0)
            return
        self._list_host.adjustSize()
        content_height = self._list_host.sizeHint().height()
        if content_height <= 0:
            spacing = self._list_layout.spacing()
            content_height = sum(
                checkbox.sizeHint().height() for _ref, checkbox in self._checkboxes
            )
            content_height += spacing * max(0, len(self._checkboxes) - 1)
        self._list_host.setMinimumHeight(content_height)
        visible = min(EXISTING_MEASURE_RELEVANCE_LIST_MAX_HEIGHT, content_height)
        self._scroll.setMinimumHeight(visible)
        self._scroll.setMaximumHeight(visible)
        self._scroll.setFixedHeight(visible)


def add_active_checkbox_separated(form: QFormLayout, checkbox: QCheckBox) -> QWidget:
    """Oddělí stav Aktivní od seznamu „Platí pro“ malým svislým odstupem."""
    gap = QWidget()
    gap.setObjectName(EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME)
    gap.setFixedHeight(EXISTING_MEASURE_ACTIVE_GAP_PX)
    gap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    form.addRow(gap)
    form.addRow("", checkbox)
    return gap
