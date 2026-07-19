"""Klávesové a myší akce nad řádkem QTableWidget (UX-COORD-4d)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QTableWidget


class _TableRowActionsFilter(QObject):
    def __init__(
        self,
        table: QTableWidget,
        *,
        on_edit: Callable[[], None] | None = None,
        on_deactivate: Callable[[], None] | None = None,
        can_edit: Callable[[], bool] | None = None,
        can_deactivate: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(table)
        self.table = table
        self.on_edit = on_edit
        self.on_deactivate = on_deactivate
        self.can_edit = can_edit
        self.can_deactivate = can_deactivate

    def _has_selection(self) -> bool:
        return bool(self.table.selectionModel() and self.table.selectionModel().selectedRows())

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is not self.table or event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.on_edit or not self._has_selection():
                return False
            if self.can_edit is not None and not self.can_edit():
                return True
            self.on_edit()
            return True
        if key == Qt.Key.Key_Delete:
            if not self._has_selection() or self.on_deactivate is None:
                return True
            if self.can_deactivate is not None and not self.can_deactivate():
                # Neaktivní / nepovolená deaktivace: handler zobrazí info / zákaz.
                self.on_deactivate()
                return True
            self.on_deactivate()
            return True
        return False


def install_table_row_actions(
    table: QTableWidget,
    *,
    on_edit: Callable[[], None] | None = None,
    on_deactivate: Callable[[], None] | None = None,
    can_edit: Callable[[], bool] | None = None,
    can_deactivate: Callable[[], bool] | None = None,
    connect_double_click: bool = False,
) -> None:
    """Enter/Return = Upravit, Delete = Deaktivovat.

    ``connect_double_click=True`` jen pokud tabulka ještě nemá vlastní doubleClicked.
    ``can_edit`` / ``can_deactivate`` obvykle mapují stav tlačítek; při False se
    u Delete stejně volá handler (zobrazí „již neaktivní“ / zákaz).
    """
    if getattr(table, "_row_actions_installed", False):
        return
    table._row_actions_installed = True
    filtr = _TableRowActionsFilter(
        table,
        on_edit=on_edit,
        on_deactivate=on_deactivate,
        can_edit=can_edit,
        can_deactivate=can_deactivate,
    )
    table._row_actions_filter = filtr
    table.installEventFilter(filtr)
    if connect_double_click and on_edit is not None:
        table.doubleClicked.connect(lambda _index: on_edit())
