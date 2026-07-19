"""Obnova výběru řádku po refreshi tabulky podle stabilního ID (UX-COORD-5)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget


def find_table_row_by_id(
    table: QTableWidget,
    record_id: int,
    *,
    id_column: int = 0,
) -> int | None:
    """Vrátí index řádku se zadaným ID, nebo None."""
    for row in range(table.rowCount()):
        item = table.item(row, id_column)
        if item is None:
            continue
        try:
            if int(item.text()) == int(record_id):
                return row
        except (TypeError, ValueError):
            continue
    return None


def refresh_and_restore_selection(
    table: QTableWidget,
    record_id: int | None,
    fallback_row: int | None = None,
    *,
    id_column: int = 0,
    scroll: bool = True,
    preserve_scroll_value: int | None = None,
    focus: bool = True,
) -> bool:
    """Po načtení dat obnoví výběr podle ID (ne podle čísla řádku).

    Pokud ``record_id`` v tabulce není (např. skryté filtrem po deaktivaci):
    - vybere řádek na ``fallback_row`` (následující po posunu),
    - jinak předchozí ``fallback_row - 1``,
    - jinak výběr zruší.
    """
    target_row: int | None = None
    if record_id is not None:
        target_row = find_table_row_by_id(table, record_id, id_column=id_column)

    if target_row is None and fallback_row is not None and table.rowCount() > 0:
        if 0 <= fallback_row < table.rowCount():
            target_row = fallback_row
        elif fallback_row > 0:
            target_row = min(fallback_row - 1, table.rowCount() - 1)
        else:
            target_row = 0

    if target_row is None:
        table.clearSelection()
        if focus:
            table.setFocus(Qt.FocusReason.OtherFocusReason)
        return False

    table.selectRow(target_row)
    item = table.item(target_row, id_column)
    if item is None:
        for column in range(table.columnCount()):
            item = table.item(target_row, column)
            if item is not None:
                break

    if preserve_scroll_value is not None:
        table.verticalScrollBar().setValue(preserve_scroll_value)
    elif scroll and item is not None:
        table.scrollToItem(item, QAbstractItemView.ScrollHint.EnsureVisible)

    if focus:
        table.setFocus(Qt.FocusReason.OtherFocusReason)
    return True


def current_table_row(table: QTableWidget) -> int | None:
    selected = table.selectionModel().selectedRows() if table.selectionModel() else []
    if not selected:
        return None
    return int(selected[0].row())
